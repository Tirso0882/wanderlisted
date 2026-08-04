"""Stage 4: Multi-Agent Supervisor Graph using LangGraph.

Parallel multi-agent architecture using Send() fan-out: the supervisor
decides which discovery specialists are needed and dispatches each one as an
independent graph node via Send().  This gives per-agent checkpointing,
individual retry on failure, dedicated traces in LangGraph Studio, and
native per-agent streaming. A typed draft selects exact places after fan-in;
Transportation, Budget, and Itinerary then consume those artifacts sequentially.

Flow (intake → safety preflight → Send() fan-out → sequential phase):
    START → triage → intake → supervisor → readiness_preflight
                                        → safety_review (HITL when high risk)
                                        → readiness details
                                        ──Send──┬── flights ─────┐
                                                ├── restaurants ─┤ → component_gate
                                                └── activities ──┘
                                                               → trip_skeleton
                                                               → hotel_stay Send fan-out
                                                               → hotel_gate → draft_itinerary
                                                               → transportation
                                                                 → budget → budget_review (HITL)
                                                                 → itinerary → human_review (HITL)
                                                                     → render_handbook → END

HITL gates:
    - safety_review: interrupts when advisory is "do not travel" / "red"
    - budget_review: interrupts on a reliable material target-budget overage
    - human_review: interrupts to let user review/edit day plans before rendering

Usage:
    from src.agent.stage4_graph import graph
    result = graph.invoke(
        {"messages": [HumanMessage("Plan my Tokyo trip")]},
        {"configurable": {"thread_id": "abc"}},
    )

    # If interrupted, resume with:
    from langgraph.types import Command
    result = graph.invoke(Command(resume={"approved": True}), config)
"""

import asyncio
import json
import os

import functools

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Send
from langsmith import traceable

from custom_logging import AppLogger
from src.agent.llm import get_llm
from src.agent.nodes import component_gate_node, intake_node, trip_skeleton_node
from src.agent.policies import classify_component_result, requested_agents
from src.agent.state import TravelAgentState
from src.agent.prompts import (
    HOTEL_STAY_SEARCH_PROMPT,
    READINESS_CONSTRAINTS_CONTEXT_PROMPT,
    SHALLOW_REPLY_SYSTEM_PROMPT,
    SPECIALIST_RESULTS_CONTEXT_PROMPT,
    SUPERVISOR_EXISTING_DATA_PROMPT,
    SUPERVISOR_ROUTING_QUERY_PROMPT,
    SYNTHESIZE_SYSTEM_PROMPT,
    TRIP_REQUEST_CONTEXT_PROMPT,
    TRIAGE_SYSTEM_PROMPT,
    USER_PROFILE_CONTEXT_PROMPT,
)
from src.models import (
    AdvisoryLevel,
    BudgetBreakdown,
    BudgetCoverageStatus,
    BudgetReviewAction,
    BudgetReviewDecision,
    BudgetVerdict,
    CityStay,
    ComponentResult,
    ComponentStatus,
    ErrorCategory,
    ConversionRateRecord,
    ConversionStatus,
    PriceEvidence,
    ReadinessTopic,
    RequestScope,
    TripRequest,
    TripSkeleton,
)
from src.budget import BudgetContext
from src.models.itinerary import (
    DayRoute,
    DraftItinerary,
    ItineraryPlan,
    PlaceRef,
    RouteLeg,
    RoutePlan,
)
from src.itinerary import (
    ItineraryAssemblyContext,
    ItinerarySelectionContext,
    ItineraryValidationError,
    build_evidence_catalog,
    compute_artifact_fingerprint,
)
from src.agent.renderer import HandbookRenderer
from src.readiness import TravelReadinessReport
from src.readiness.planning import (
    readiness_request_fingerprint,
    requested_topics,
)
from src.agent.agents import (
    SupervisorAgent,
    FlightsAgent,
    HotelsAgent,
    TravelReadinessAgent,
    BudgetAgent,
    RestaurantsAgent,
    ActivitiesAgent,
    TransportationAgent,
    ItineraryAgent,
)
from src.tools.google_maps import compute_day_route_data
from src.tools.iata import resolve_iata_code

import config as app_config

# ── Routing lists from config (with sensible defaults) ────────────────────
_routing_cfg = app_config.get("routing") or {}

DEPENDENT_TRANSPORTATION_AGENT = "TransportationAgent"

PARALLEL_AGENTS = [
    agent
    for agent in _routing_cfg.get(
        "parallel_agents",
        [
            "FlightsAgent",
            "HotelsAgent",
            "TravelReadinessAgent",
            "RestaurantsAgent",
            "ActivitiesAgent",
        ],
    )
    if agent not in {DEPENDENT_TRANSPORTATION_AGENT, "HotelsAgent"}
]
SEQUENTIAL_AGENTS = _routing_cfg.get(
    "sequential_agents",
    [
        "HotelsAgent",
        DEPENDENT_TRANSPORTATION_AGENT,
        "BudgetAgent",
        "ItineraryAgent",
    ],
)

ALL_AGENTS = PARALLEL_AGENTS + SEQUENTIAL_AGENTS

AGENT_TO_NODE = {
    "FlightsAgent": "flights",
    "HotelsAgent": "hotels",
    "TravelReadinessAgent": "readiness",
    "BudgetAgent": "budget",
    "RestaurantsAgent": "restaurants",
    "ActivitiesAgent": "activities",
    "TransportationAgent": "transportation",
    "ItineraryAgent": "itinerary",
}

# Reverse map for context building
DATA_KEYS = list(AGENT_TO_NODE.values())

# ── HITL gate toggles (env vars override config) ──────────────────────────
_hitl_cfg = app_config.get("hitl") or {}


def is_hitl_enabled(gate: str) -> bool:
    """Check if a specific HITL gate is enabled.

    Priority: env var HITL_{GATE}_ENABLED > config/config.yaml > default (True).
    """
    env_key = f"HITL_{gate.upper()}"
    env_val = os.environ.get(env_key)
    if env_val is not None:
        return env_val.lower() in ("1", "true", "yes")
    return _hitl_cfg.get(gate, True)


# ── Helper functions (module-level, testable) ─────────────────────────────


def build_user_profile_context(state: TravelAgentState) -> str:
    """Build a profile context string from state for subagent injection."""
    parts = []
    if state.get("destinations"):
        parts.append(f"Destinations: {', '.join(state['destinations'])}")
    if state.get("travel_style"):
        parts.append(f"Travel style: {state['travel_style']}")
    if state.get("group_type"):
        parts.append(f"Group type: {state['group_type']}")
    if state.get("accessibility_needs"):
        parts.append(f"Accessibility needs: {', '.join(state['accessibility_needs'])}")
    if state.get("dietary_restrictions"):
        parts.append(
            f"Dietary restrictions: {', '.join(state['dietary_restrictions'])}"
        )
    if not parts:
        return ""
    return USER_PROFILE_CONTEXT_PROMPT.format(profile="\n".join(parts))


def build_trip_request_context(state: TravelAgentState) -> str:
    """Serialize canonical request fields so specialists do not re-parse history."""
    request_data = state.get("trip_request", {})
    if not request_data:
        return ""
    request = TripRequest.model_validate(request_data)
    return TRIP_REQUEST_CONTEXT_PROMPT.format(
        canonical_request=json.dumps(
            request.model_dump(mode="json"), ensure_ascii=False
        )
    )


def build_readiness_constraints_context(state: TravelAgentState) -> str:
    """Serialize only grounded constraints intended for downstream operations."""
    components = state.get("itinerary_components", {})
    raw_report = components.get("readiness", {}).get("data") or components.get(
        "readiness_preflight", {}
    ).get("data")
    if not raw_report:
        return ""
    try:
        report = TravelReadinessReport.model_validate(raw_report)
    except Exception:
        _log.warning("Ignoring invalid readiness data in downstream context")
        return ""
    if not report.planning_constraints:
        return ""
    payload = [
        constraint.model_dump(mode="json") for constraint in report.planning_constraints
    ]
    return READINESS_CONSTRAINTS_CONTEXT_PROMPT.format(
        constraints=json.dumps(payload, ensure_ascii=False)
    )


def build_context_messages(
    state: TravelAgentState,
    *,
    readiness_context: str = "full",
) -> list:
    """Build message list enriched with results from prior agents and user profile.

    Checks for data keys directly rather than the per-invocation
    completed_agents list, so context is available both within a single
    run AND across follow-up turns.
    """
    components = state.get("itinerary_components", {})
    label_map = {
        "flights": "Flights results",
        "hotels": "Hotels results",
        "readiness": "Travel readiness results",
        "budget": "Budget results",
        "restaurants": "Restaurants results",
        "activities": "Activities results",
        "trip_skeleton": "Exact trip dates and city stays",
        "draft_itinerary": "Selected draft itinerary",
        "transportation": "Transportation results",
        "itinerary": "Itinerary results",
    }

    parts = []
    for key, label in label_map.items():
        if readiness_context != "full" and key == "readiness":
            continue
        if key in components:
            agent_msgs = components[key].get("messages", [])
            summary = " ".join(
                _extract_text_content(m.content)
                for m in agent_msgs
                if isinstance(m, AIMessage) and m.content
            )
            if summary:
                parts.append(f"[{label}]\n{summary}")

    msgs = list(state["messages"])

    request_context = build_trip_request_context(state)
    if request_context:
        msgs.insert(0, SystemMessage(content=request_context))

    # Inject user profile
    profile = build_user_profile_context(state)
    if profile:
        msgs.insert(0, SystemMessage(content=profile))

    if readiness_context == "constraints":
        constraint_context = build_readiness_constraints_context(state)
        if constraint_context:
            msgs.insert(0, SystemMessage(content=constraint_context))

    if parts:
        context = SPECIALIST_RESULTS_CONTEXT_PROMPT.format(results="\n\n".join(parts))
        msgs.insert(0, SystemMessage(content=context))
    return msgs


# ── Generic agent runner (module-level) ───────────────────────────────────


@traceable(run_type="chain", name="specialist_agent_run")
async def run_agent(
    agent_name: str,
    state: TravelAgentState,
    *,
    executors: dict,
) -> dict:
    """Run a single specialist agent and return its results dict."""
    executor = executors[agent_name]
    enriched = build_context_messages(state)
    result = await executor.ainvoke({"messages": enriched})
    new_msgs = result["messages"][len(enriched) :]
    return {
        "messages": new_msgs,
        "data_key": AGENT_TO_NODE[agent_name],
        "result": result,
    }


# ── HITL gate nodes (module-level, testable) ──────────────────────────────


def _normalize_hitl_decision(decision) -> dict:
    """Normalize the resume value from interrupt() into a dict.

    LangGraph Studio may send the resume value as a string, bool, or dict
    depending on how the user types it (YAML vs RAW mode).  This helper
    ensures the HITL gate nodes always see a consistent dict.
    """
    if isinstance(decision, dict):
        action = str(decision.get("action", "")).strip().lower()
        if action in {"approved", "proceed"}:
            return {**decision, "approved": True}
        if action == "edited":
            return {**decision, "approved": True}
        if action in {"rejected", "cancel"}:
            return {**decision, "approved": False}
        return decision
    if isinstance(decision, bool):
        return {"approved": decision}
    if isinstance(decision, str):
        lowered = decision.strip().lower()
        # Handle bare true/false
        if lowered in ("true", "yes", "approve", "approved", "ok", "proceed"):
            return {"approved": True}
        if lowered in ("false", "no", "reject", "rejected", "cancel"):
            return {"approved": False}
        # Handle JSON-like string: '{"approved": true}'
        import json

        try:
            parsed = json.loads(decision)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, bool):
                return {"approved": parsed}
        except (json.JSONDecodeError, TypeError):
            pass
        # Handle YAML-style "approved: true" as a plain string
        if "approved" in lowered:
            if "true" in lowered or "yes" in lowered:
                return {"approved": True, "feedback": ""}
            return {"approved": False}
        # Unknown string — treat as feedback with approval
        return {"approved": True, "feedback": decision.strip()}
    # Fallback
    return {"approved": bool(decision)}


async def safety_review_node(state: TravelAgentState) -> dict:
    """HITL gate: interrupt when safety advisory is 'do not travel' or 'red'.

    Checks the completed readiness preflight for dangerous advisory levels.
    If dangerous, pauses execution so the user can acknowledge the risk
    or cancel the trip.

    Can be disabled explicitly for non-interactive clients.
    """
    components = state.get("itinerary_components", {})
    preflight_component = components.get("readiness_preflight")

    def approved_update(**extra) -> dict:
        """Expose verified preflight data under the canonical readiness key."""
        result = {
            "current_agent": "safety_review",
            "hitl_action": "approved",
            **extra,
        }
        if preflight_component:
            result["itinerary_components"] = {"readiness": preflight_component}
            preflight_outcome = state.get("component_results", {}).get(
                "readiness_preflight"
            )
            if preflight_outcome:
                readiness_outcome = dict(preflight_outcome)
                readiness_outcome["component"] = "readiness"
                result["component_results"] = {"readiness": readiness_outcome}
        return result

    destination_data = (
        components.get("readiness_preflight") or components.get("readiness") or {}
    )

    report_data = destination_data.get("data")
    if not report_data:
        return {
            "messages": [
                AIMessage(
                    content="Official safety evidence could not be validated, so discovery was not started."
                )
            ],
            "current_agent": "safety_review",
            "hitl_action": "rejected",
        }
    try:
        report = TravelReadinessReport.model_validate(report_data)
    except Exception:
        _log.warning("Ignoring invalid structured readiness report at safety gate")
        return {
            "messages": [
                AIMessage(
                    content="Official safety evidence could not be validated, so discovery was not started."
                )
            ],
            "current_agent": "safety_review",
            "hitl_action": "rejected",
        }

    request_data = state.get("trip_request")
    if request_data:
        request = TripRequest.model_validate(request_data)
        expected_fingerprint = readiness_request_fingerprint(
            request,
            requested_topics(_latest_human_question(state), request)
            | {ReadinessTopic.SAFETY},
        )
        outcomes = state.get("component_results", {})
        preflight_outcome = outcomes.get("readiness_preflight") or outcomes.get(
            "readiness", {}
        )
        if preflight_outcome.get("request_fingerprint") != expected_fingerprint:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "The saved safety preflight no longer matches the current "
                            "destinations, passport, dates, or topics, so discovery "
                            "was not started."
                        )
                    )
                ],
                "current_agent": "safety_review",
                "hitl_action": "rejected",
            }

    coverage_items = destination_data.get("coverage", {}).get("items", [])
    verified_destinations = {
        str(item.get("destination", "")).strip().lower()
        for item in coverage_items
        if item.get("topic") == ReadinessTopic.SAFETY
        and item.get("state") == "verified"
    }
    if verified_destinations != set(report.destinations):
        return {
            "messages": [
                AIMessage(
                    content=(
                        "An officially grounded advisory was not verified for every "
                        "destination, so discovery was not started."
                    )
                )
            ],
            "current_agent": "safety_review",
            "hitl_action": "rejected",
        }

    advisory_source_ids = report.citations.get("safety.advisory_level", [])
    source_by_id = {source.id: source for source in report.sources}
    has_official_advisory = (
        bool(advisory_source_ids)
        and all(
            source_by_id[source_id].is_official
            for source_id in advisory_source_ids
            if source_id in source_by_id
        )
        and all(source_id in source_by_id for source_id in advisory_source_ids)
    )
    if not has_official_advisory:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "An officially cited advisory was not verified for every "
                        "destination, so discovery was not started."
                    )
                )
            ],
            "current_agent": "safety_review",
            "hitl_action": "rejected",
        }

    # Disabling HITL disables only the user interrupt. Evidence validation is
    # still mandatory before readiness data can reach discovery agents.
    if not is_hitl_enabled("safety_review"):
        return approved_update()

    # Only a typed dangerous level with cited official evidence may interrupt.
    is_dangerous = has_official_advisory and report.safety.advisory_level in {
        AdvisoryLevel.ORANGE,
        AdvisoryLevel.RED,
    }

    if is_dangerous and not state.get("safety_acknowledged"):
        safety_snippet = report.safety.advisory_summary[:500]

        raw_decision = interrupt(
            {
                "type": "safety_warning",
                "gate": "safety_review",
                "advisory_level": str(report.safety.advisory_level),
                "summary": safety_snippet,
                "message": (
                    "⚠️ SAFETY ADVISORY: The destination has a high-risk travel advisory. "
                    "Review the safety information and decide whether to proceed."
                ),
                "details": safety_snippet,
                "action_required": "Respond with true to proceed or false to cancel.",
            }
        )
        decision = _normalize_hitl_decision(raw_decision)

        if not decision.get("approved", False):
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "🛑 Trip planning cancelled due to safety advisory. "
                            "Consider alternative destinations or check back when conditions improve."
                        )
                    )
                ],
                "current_agent": "safety_review",
                "hitl_action": "rejected",
            }

        return approved_update(safety_acknowledged=True)

    # No safety concern — pass through
    return approved_update()


async def budget_review_node(state: TravelAgentState) -> dict:
    """Pause only for a sufficiently covered, material target-budget overage."""
    if not is_hitl_enabled("budget_review"):
        return {"current_agent": "budget_review", "hitl_action": "proceed"}

    components = state.get("itinerary_components", {})
    budget_data = components.get("budget_structured", {})
    if not budget_data:
        return {"current_agent": "budget_review", "hitl_action": "proceed"}
    try:
        budget = BudgetBreakdown.model_validate(budget_data)
    except ValueError:
        return {"current_agent": "budget_review", "hitl_action": "proceed"}

    reliable = (
        budget.coverage_status != BudgetCoverageStatus.PARTIAL
        and budget.conversion_status != ConversionStatus.UNAVAILABLE
        and budget.display_conversion_available
        and budget.verdict == BudgetVerdict.OVER_BUDGET
        and budget.target_budget > 0
        and abs(budget.reconciliation_delta) < 0.01
    )
    overspend = budget.total - budget.target_budget
    threshold = max(
        budget.target_budget
        * float(app_config.get("budget", "review_overage_percent", 10))
        / 100,
        float(app_config.get("budget", "review_overage_floor_usd", 100)),
    )
    if (
        reliable
        and overspend >= threshold
        and not state.get("budget_adjustment_accepted")
    ):
        raw_decision = interrupt(
            {
                "type": "budget_warning",
                "gate": "budget_review",
                "message": (
                    f"Estimated trip cost (USD {budget.total:,.2f}) exceeds the "
                    f"target (USD {budget.target_budget:,.2f}) by USD {overspend:,.2f}."
                ),
                "summary": budget.summary,
                "estimated_total": budget.total,
                "target_budget": budget.target_budget,
                "overspend": overspend,
                "threshold": threshold,
                "currency": "USD",
                "display_breakdown": (
                    budget.display_breakdown.model_dump(mode="json")
                    if budget.display_breakdown
                    else None
                ),
                "display_currency": budget.display_currency,
                "display_conversion_available": budget.display_conversion_available,
                "suggestions": [
                    "Review the selected flight and hotel rates",
                    "Reduce trip duration or optional paid activities",
                    "Set a higher target only if that reflects your actual limit",
                ],
                "action_required": "Proceed, adjust the target, or cancel.",
            }
        )
        normalised = _normalize_hitl_decision(raw_decision)
        if "action" not in normalised:
            normalised = {
                "gate": "budget_review",
                "action": (
                    "proceed" if normalised.get("approved", False) else "cancel"
                ),
            }
        try:
            decision = BudgetReviewDecision.model_validate(normalised)
        except ValueError:
            decision = BudgetReviewDecision(action=BudgetReviewAction.CANCEL)

        if decision.action == BudgetReviewAction.CANCEL:
            return {
                "messages": [
                    AIMessage(
                        content="Budget review cancelled the remaining planning workflow."
                    )
                ],
                "current_agent": "budget_review",
                "hitl_action": "cancel",
            }
        if decision.action == BudgetReviewAction.ADJUST_TARGET:
            request = TripRequest.model_validate(state.get("trip_request", {}))
            adjusted = request.model_copy(update={"budget_amount": decision.new_budget})
            return {
                "current_agent": "budget_review",
                "trip_request": adjusted.model_dump(mode="json"),
                "budget_adjustment_accepted": False,
                "hitl_action": "adjust_target",
            }
        return {
            "current_agent": "budget_review",
            "budget_adjustment_accepted": True,
            "hitl_action": "proceed",
        }

    return {"current_agent": "budget_review", "hitl_action": "proceed"}


async def human_review_node(state: TravelAgentState) -> dict:
    """HITL gate: let the user review the assembled itinerary before rendering.

    Pauses to show a summary of the itinerary components and allows
    the user to approve, request edits, or reject.

    Disabled when hitl.human_review = false (webapp mode).
    """
    if not is_hitl_enabled("human_review"):
        return {"current_agent": "human_review", "hitl_action": "approved"}

    components = state.get("itinerary_components", {})
    itinerary_data = components.get("itinerary", {})
    structured_plan = components.get("itinerary_structured")

    # Build a summary of what was assembled
    summary_parts = []
    if "flights" in components:
        summary_parts.append("✈️ Flights: found")
    if "hotels" in components:
        summary_parts.append("🏨 Hotels: found")
    if "restaurants" in components:
        summary_parts.append("🍽️ Restaurants: found")
    if "activities" in components:
        summary_parts.append("🎯 Activities: found")
    if "readiness" in components:
        summary_parts.append("🛡️ Travel essentials: found")
    if "transportation" in components:
        summary_parts.append("🚃 Transportation: found")
    if "budget" in components:
        summary_parts.append("💰 Budget: calculated")
    if "itinerary" in components:
        summary_parts.append("📅 Itinerary: assembled")

    itinerary_preview = ""
    if structured_plan:
        try:
            plan = ItineraryPlan.model_validate(structured_plan)
            preview_lines = [
                f"{plan.start_date} to {plan.end_date} — {plan.feasibility_status}"
            ]
            for day in plan.days:
                names = [
                    place.name
                    for block in day.time_blocks
                    for place in (
                        [*block.activities]
                        + ([block.restaurant] if block.restaurant else [])
                    )
                ]
                preview_lines.append(
                    f"Day {day.day_number} ({day.date}, {day.city}): "
                    + (", ".join(names) if names else "no scheduled stops")
                )
            itinerary_preview = "\n".join(preview_lines)[:2000]
        except ValueError:
            itinerary_preview = ""
    if not itinerary_preview:
        for m in itinerary_data.get("messages", []):
            if isinstance(m, AIMessage) and m.content:
                itinerary_preview += _extract_text_content(m.content)[:2000]
                break

    raw_decision = interrupt(
        {
            "type": "itinerary_review",
            "gate": "human_review",
            "summary": "Review the validated, typed itinerary before handbook generation.",
            "message": "📋 Your travel plan is ready for review before generating the final handbook.",
            "components_available": summary_parts,
            "itinerary_preview": itinerary_preview[:2000],
            "action_required": (
                "Respond with true to generate the handbook, "
                "provide feedback text to proceed with notes, "
                "or false to cancel."
            ),
        }
    )
    decision = _normalize_hitl_decision(raw_decision)

    if not decision.get("approved", False):
        return {
            "messages": [
                AIMessage(
                    content=(
                        "📝 Handbook generation cancelled. Let me know what you'd like to change "
                        "and I'll adjust the itinerary."
                    )
                )
            ],
            "current_agent": "human_review",
            "hitl_action": "rejected",
            "human_feedback": decision.get("feedback", ""),
        }

    feedback = decision.get("feedback", "")
    if feedback:
        unsupported_edits = (
            "change the date",
            "change dates",
            "different dates",
            "extend the trip",
            "shorten the trip",
            "add a city",
            "new destination",
            "change destination",
            "change the flight",
            "different flight",
            "new flight",
            "change the budget",
            "increase the budget",
        )
        if any(phrase in feedback.casefold() for phrase in unsupported_edits):
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "That edit changes a canonical trip input or requires new "
                            "provider evidence. Please confirm the new trip details so "
                            "the affected specialists can run explicitly."
                        )
                    )
                ],
                "current_agent": "human_review:needs_clarification",
                "workflow_status": "needs_user_input",
                "pending_questions": [
                    "Please confirm the new dates, destination, flight, or budget details."
                ],
                "hitl_action": "needs_clarification",
                "human_feedback": feedback,
            }
        edit_routing = list(components.get("routing", []))
        for agent_name in (
            DEPENDENT_TRANSPORTATION_AGENT,
            "BudgetAgent",
            "ItineraryAgent",
        ):
            if agent_name not in edit_routing:
                edit_routing.append(agent_name)
        return {
            "messages": [
                AIMessage(
                    content=(
                        f"📝 Noted your feedback: {feedback}. "
                        "I will revalidate the selection and dependent routes before rendering."
                    )
                )
            ],
            "current_agent": "human_review",
            "hitl_action": "edited",
            "human_feedback": feedback,
            "itinerary_components": {"routing": edit_routing},
        }

    return {
        "current_agent": "human_review",
        "hitl_action": "approved",
    }


# ── Background logging (fire-and-forget) ─────────────────────────────────


async def _bg_log_to_langsmith(
    paths: dict[str, str],
    destinations: list[str],
    sections: list[str],
) -> None:
    """Fire-and-forget: log handbook generation metadata to LangSmith.

    Called via ``asyncio.create_task`` so the graph node returns to the user
    immediately without waiting for the LangSmith HTTP round-trip to complete.
    Failures are silently ignored — logging is best-effort.
    """
    try:
        from langsmith import Client

        def _sync_log() -> None:
            client = Client()
            client.create_run(
                project_name=os.environ.get("LANGCHAIN_PROJECT", "wanderlisted"),
                name="handbook_output",
                run_type="chain",
                inputs={"destinations": destinations, "sections": sections},
                outputs={"paths": paths},
                tags=["handbook", "output"],
                end_time=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
            )

        await asyncio.to_thread(_sync_log)
    except asyncio.CancelledError:
        pass  # Task cancelled (e.g. event loop closing at end of a test)
    except Exception:
        pass  # Best-effort — never let background logging surface to the user


# ── Content extraction (Responses API returns list, Chat Completions returns string) ──


def _extract_text_content(content) -> str:
    """Extract text from LangChain message.content.

    When use_responses_api=True, content is a list of content blocks:
        [{"type": "text", "text": "...", ...}, ...]

    When use_responses_api=False (Chat Completions), content is a string:
        "..."
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Responses API format
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if text:
                    texts.append(text)
        return " ".join(texts)
    # Fallback for unknown formats
    return str(content or "")


# ── Node functions (module-level, testable via dependency injection) ───────


@traceable(run_type="chain", name="triage_node", tags=["wanderlisted", "triage"])
async def triage_node(state: TravelAgentState, *, llm) -> dict:
    """Lightweight classifier: decide if the query needs the full pipeline (deep)
    or can be answered directly (shallow)."""
    last_message = state["messages"][-1]
    response = await llm.ainvoke(
        [
            SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
            HumanMessage(content=last_message.content),
        ]
    )
    classification = _extract_text_content(response.content).strip().lower()
    # Default to deep if the LLM returns anything unexpected
    route = "shallow" if classification == "shallow" else "deep"
    return {"current_agent": f"triage:{route}"}


@traceable(
    run_type="chain", name="shallow_reply_node", tags=["wanderlisted", "shallow"]
)
async def shallow_reply_node(state: TravelAgentState, *, llm) -> dict:
    """Answer simple queries (greetings, confirmations, clarifications)
    without invoking the supervisor or any specialist agents."""
    enriched = build_context_messages(state)
    response = await llm.ainvoke(
        [
            SystemMessage(content=SHALLOW_REPLY_SYSTEM_PROMPT),
            *enriched,
        ]
    )
    return {"messages": [response], "current_agent": "shallow_reply"}


@traceable(
    run_type="chain", name="supervisor_node", tags=["wanderlisted", "supervisor"]
)
async def supervisor_node(state: TravelAgentState, *, supervisor_agent) -> dict:
    """Use the LLM to classify the query and decide which specialists to invoke."""
    components = state.get("itinerary_components", {})

    # Tell the supervisor what data already exists
    data_parts = []
    label_map = {
        "flights": "FlightsAgent: flight search results",
        "hotels": "HotelsAgent: hotel results",
        "readiness": "TravelReadinessAgent: safety, weather, entry, health, and culture",
        "budget": "BudgetAgent: budget breakdown",
        "restaurants": "RestaurantsAgent: restaurant recommendations",
        "activities": "ActivitiesAgent: activity and attraction results",
        "transportation": "TransportationAgent: transport and route info",
        "itinerary": "ItineraryAgent: assembled itinerary",
    }
    for key, desc in label_map.items():
        outcome = state.get("component_results", {}).get(key, {})
        status = outcome.get("status")
        if status == ComponentStatus.COMPLETED or (
            status is None and key in components
        ):
            data_parts.append(f"- {desc} already collected")

    existing_summary = ""
    if data_parts:
        existing_summary = SUPERVISOR_EXISTING_DATA_PROMPT.format(
            data_summary="\n".join(data_parts)
        )

    # Single-agent isolation: skip LLM routing, force to target agent only
    target = state.get("target_agent", "")
    if target and target in AGENT_TO_NODE:
        return {
            "messages": [AIMessage(content=f"Routing to {target}...")],
            "current_agent": "supervisor",
            "itinerary_components": {
                **components,
                "routing": [target],
                "completed_agents": [],
            },
        }

    last_message = state["messages"][-1]
    latest_text = _extract_text_content(last_message.content)
    canonical_data = state.get("trip_request", {})
    canonical_request = TripRequest.model_validate(canonical_data)
    routing_query = latest_text
    if canonical_data:
        routing_query = SUPERVISOR_ROUTING_QUERY_PROMPT.format(
            latest_message=latest_text,
            canonical_request=json.dumps(
                canonical_request.model_dump(mode="json"), ensure_ascii=False
            ),
        )
    decision = await supervisor_agent.aget_routing_decision(
        routing_query,
        existing_summary,
    )

    # Product capabilities extracted by intake are authoritative. The supervisor
    # still supplies reasoning/user-facing text, but cannot forget earlier turns.
    authoritative_agents = requested_agents(canonical_request)
    if authoritative_agents:
        decision.agents = authoritative_agents

    # Merge user profile: keep existing values, override only if new non-empty
    new_destinations = decision.destinations or state.get("destinations", [])
    new_travel_style = decision.travel_style or state.get("travel_style", "")
    new_group_type = decision.group_type or state.get("group_type", "")
    new_accessibility = decision.accessibility_needs or state.get(
        "accessibility_needs", []
    )
    new_dietary = decision.dietary_restrictions or state.get("dietary_restrictions", [])

    return {
        "messages": [AIMessage(content=decision.user_message)],
        "current_agent": "supervisor",
        "destinations": new_destinations,
        "travel_style": new_travel_style,
        "group_type": new_group_type,
        "accessibility_needs": new_accessibility,
        "dietary_restrictions": new_dietary,
        "itinerary_components": {
            **components,
            "routing": decision.agents,
            "completed_agents": [],
        },
    }


# ── Specialist execution nodes ───────────────────────────────────────────
#
# Discovery specialists are independent LangGraph nodes dispatched through
# Send(). LangGraph fans them in before the completion gate; transportation
# later uses the validated merged results as a dependent specialist.
# Only writing the agent's own key to itinerary_components (not the full
# dict) is intentional: the _merge_components reducer in TravelAgentState
# accumulates each worker's partial write without overwriting the others.

_log = AppLogger("agent.stage4_graph")


async def _run_parallel_agent(
    state: TravelAgentState,
    *,
    executor,
    agent_name: str,
) -> dict:
    """Execute a specialist agent with error handling.

    If the agent fails (e.g. external API down), log the error and return a
    graceful degradation message instead of crashing the whole graph.
    """
    downstream_specialists = {
        "flights",
        "hotels",
        "restaurants",
        "activities",
        "transportation",
    }
    enriched = build_context_messages(
        state,
        readiness_context=(
            "constraints" if agent_name in downstream_specialists else "full"
        ),
    )
    try:
        result = await executor.ainvoke({"messages": enriched})
        new_msgs = result["messages"][len(enriched) :]
        outcome = classify_component_result(agent_name, new_msgs)
        return {
            "messages": new_msgs,
            "current_agent": agent_name,
            "itinerary_components": {agent_name: result},
            "component_results": {
                agent_name: outcome.model_dump(mode="json"),
            },
        }
    except Exception as exc:
        _log.warning(
            "%s agent failed (graph will continue): %s: %s",
            agent_name,
            type(exc).__name__,
            exc,
        )
        error_msg = AIMessage(
            content=(
                f"[{agent_name.title()} Agent] I was unable to gather "
                f"{agent_name} data due to a temporary service issue. "
                "Planning has paused so incomplete data is not presented as final."
            ),
        )
        outcome = classify_component_result(agent_name, [], error=exc)
        return {
            "messages": [error_msg],
            "current_agent": agent_name,
            "itinerary_components": {agent_name: {"error": type(exc).__name__}},
            "component_results": {
                agent_name: outcome.model_dump(mode="json"),
            },
        }


@traceable(run_type="chain", name="flights_node", tags=["wanderlisted", "flights"])
async def flights_node(state: TravelAgentState, *, executor) -> dict:
    """Fan-out worker: run FlightsAgent as an independent graph node."""
    return await _run_parallel_agent(state, executor=executor, agent_name="flights")


@traceable(run_type="chain", name="hotels_node", tags=["wanderlisted", "hotels"])
async def hotels_node(state: TravelAgentState, *, executor) -> dict:
    """Fan-out worker: run HotelsAgent as an independent graph node."""
    return await _run_parallel_agent(state, executor=executor, agent_name="hotels")


@traceable(
    run_type="chain",
    name="hotel_stay_node",
    tags=["wanderlisted", "hotels", "city-stay"],
)
async def hotel_stay_node(state: TravelAgentState, *, executor) -> dict:
    """Search Hotelbeds for one exact CityStay selected by TripSkeleton."""
    stay = CityStay.model_validate(state.get("active_hotel_stay", {}))
    request = TripRequest.model_validate(state.get("trip_request", {}))
    city_code = resolve_iata_code(stay.city)
    stay_key = f"stay-{stay.sequence}"

    if city_code is None:
        message = AIMessage(
            content=f"No IATA/Hotelbeds city code found for {stay.city}."
        )
        outcome = ComponentResult(
            component="hotels",
            status=ComponentStatus.FAILED,
            message=_extract_text_content(message.content),
            error_category=ErrorCategory.VALIDATION,
            error_detail=f"Could not resolve city code for {stay.city}",
        )
        return {
            "messages": [message],
            "current_agent": f"hotels:{stay.city}:failed",
            "hotel_search_results": {
                stay_key: {
                    "stay": stay.model_dump(mode="json"),
                    "city_code": "",
                    "messages": [message],
                    "outcome": outcome.model_dump(mode="json"),
                }
            },
        }

    travelers = request.travelers
    children_ages = ",".join(str(age) for age in travelers.child_ages)
    instruction = SystemMessage(
        content=HOTEL_STAY_SEARCH_PROMPT.format(
            city=stay.city,
            city_code=city_code,
            check_in_date=stay.check_in.isoformat(),
            check_out_date=stay.check_out.isoformat(),
            adults=travelers.adults,
            children=travelers.children,
            children_ages=children_ages,
        )
    )
    input_messages = [
        instruction,
        *build_context_messages(state, readiness_context="constraints"),
    ]
    try:
        result = await executor.ainvoke({"messages": input_messages})
        new_msgs = result["messages"][len(input_messages) :]
        outcome = classify_component_result("hotels", new_msgs)
    except Exception as exc:
        _log.warning("Hotel search failed for %s: %s", stay.city, exc)
        message = AIMessage(
            content=f"Hotel search for {stay.city} failed due to a provider error."
        )
        new_msgs = [message]
        outcome = classify_component_result("hotels", [], error=exc)

    return {
        "messages": new_msgs,
        "current_agent": f"hotels:{stay.city}",
        "hotel_search_results": {
            stay_key: {
                "stay": stay.model_dump(mode="json"),
                "city_code": city_code,
                "messages": new_msgs,
                "outcome": outcome.model_dump(mode="json"),
            }
        },
    }


@traceable(
    run_type="chain",
    name="hotel_fan_in_node",
    tags=["wanderlisted", "hotels", "fan-in"],
)
async def hotel_fan_in_node(state: TravelAgentState) -> dict:
    """Aggregate all exact city-stay searches into one hotels component."""
    searches = sorted(
        state.get("hotel_search_results", {}).values(),
        key=lambda item: item.get("stay", {}).get("sequence", 0),
    )
    all_messages = [
        message for search in searches for message in search.get("messages", [])
    ]
    statuses = [
        search.get("outcome", {}).get("status", ComponentStatus.FAILED)
        for search in searches
    ]
    if searches and all(status == ComponentStatus.COMPLETED for status in statuses):
        status = ComponentStatus.COMPLETED
    else:
        status = next(
            (
                candidate
                for candidate in (
                    ComponentStatus.NEEDS_USER_INPUT,
                    ComponentStatus.BLOCKED_EXTERNAL,
                    ComponentStatus.NO_INVENTORY,
                    ComponentStatus.FAILED,
                )
                if candidate in statuses
            ),
            ComponentStatus.FAILED,
        )

    summary = "; ".join(
        f"{search.get('stay', {}).get('city', '?')}: "
        f"{search.get('outcome', {}).get('status', 'failed')}"
        for search in searches
    )
    outcome = ComponentResult(
        component="hotels",
        status=status,
        data={
            "stays": [
                {
                    "stay": search.get("stay", {}),
                    "city_code": search.get("city_code", ""),
                    "status": search.get("outcome", {}).get("status", "failed"),
                }
                for search in searches
            ]
        },
        message=summary,
        tools_called=[
            tool
            for search in searches
            for tool in search.get("outcome", {}).get("tools_called", [])
        ],
        evidence_count=sum(
            search.get("outcome", {}).get("evidence_count", 0) for search in searches
        ),
    )
    components = state.get("itinerary_components", {})
    return {
        "current_agent": f"hotels:{status}",
        "itinerary_components": {
            **components,
            "hotels": {"messages": all_messages},
        },
        "component_results": {"hotels": outcome.model_dump(mode="json")},
    }


def _latest_human_question(state: TravelAgentState) -> str:
    return next(
        (
            _extract_text_content(message.content)
            for message in reversed(state.get("messages", []))
            if isinstance(message, HumanMessage) and message.content
        ),
        "",
    )


def _readiness_component_result(
    run, component_name: str
) -> tuple[ComponentResult, dict]:
    message = AIMessage(content=run.message)
    if run.report is None:
        outcome = ComponentResult(
            component=component_name,
            status=run.status,
            missing_fields=run.missing_fields,
            message=run.message,
            error_category=run.error_category,
            request_fingerprint=run.request_fingerprint,
        )
        return outcome, {
            "messages": [message],
            "data": None,
            "coverage": run.coverage.model_dump(mode="json"),
        }
    report_data = run.report.model_dump(mode="json")
    tools = []
    if any(source.domain == "open-meteo.com" for source in run.report.sources):
        tools.append("open_meteo_forecast")
    if any(source.domain != "open-meteo.com" for source in run.report.sources):
        tools.append("tavily_search")
    outcome = ComponentResult(
        component=component_name,
        status=run.status,
        data=report_data,
        message=run.message,
        error_category=run.error_category,
        tools_called=tools,
        evidence_count=len(run.report.sources),
        request_fingerprint=run.request_fingerprint,
    )
    return outcome, {
        "messages": [message],
        "data": report_data,
        "coverage": run.coverage.model_dump(mode="json"),
    }


@traceable(
    run_type="chain",
    name="readiness_preflight_node",
    tags=["wanderlisted", "readiness", "safety"],
)
async def readiness_preflight_node(state: TravelAgentState, *, executor) -> dict:
    """Run official advisory research before any paid discovery fan-out."""
    latest = _latest_human_question(state)
    request = TripRequest.model_validate(state.get("trip_request", {}))
    try:
        run = await executor.preflight(question=latest, trip_request=request)
        outcome, component = _readiness_component_result(run, "readiness_preflight")
        return {
            "messages": component["messages"],
            "current_agent": "readiness_preflight",
            "itinerary_components": {"readiness_preflight": component},
            "component_results": {
                "readiness_preflight": outcome.model_dump(mode="json")
            },
        }
    except Exception as exc:
        _log.warning("Readiness preflight failed: %s: %s", type(exc).__name__, exc)
        outcome = classify_component_result("readiness_preflight", [], error=exc)
        message = AIMessage(
            content="I could not verify official safety advisories, so discovery was not started."
        )
        return {
            "messages": [message],
            "current_agent": "readiness_preflight",
            "itinerary_components": {
                "readiness_preflight": {"messages": [message], "data": None}
            },
            "component_results": {
                "readiness_preflight": outcome.model_dump(mode="json")
            },
        }


@traceable(run_type="chain", name="readiness_node", tags=["wanderlisted", "readiness"])
async def readiness_node(state: TravelAgentState, *, executor) -> dict:
    """Run focused or post-preflight readiness details without place discovery."""
    latest = _latest_human_question(state)
    request = TripRequest.model_validate(state.get("trip_request", {}))
    try:
        preflight_data = (
            state.get("itinerary_components", {})
            .get("readiness_preflight", {})
            .get("data")
        )
        if preflight_data:
            preflight_fingerprint = (
                state.get("component_results", {})
                .get("readiness_preflight", {})
                .get("request_fingerprint", "")
            )
            run = await executor.research_details(
                question=latest,
                trip_request=request,
                preflight_report=TravelReadinessReport.model_validate(preflight_data),
                preflight_fingerprint=preflight_fingerprint,
            )
        else:
            run = await executor.research(question=latest, trip_request=request)
        outcome, component = _readiness_component_result(run, "readiness")
        return {
            "messages": component["messages"],
            "current_agent": "readiness",
            "itinerary_components": {"readiness": component},
            "component_results": {"readiness": outcome.model_dump(mode="json")},
        }
    except Exception as exc:
        _log.warning("Readiness pipeline failed: %s: %s", type(exc).__name__, exc)
        outcome = classify_component_result("readiness", [], error=exc)
        message = AIMessage(
            content="I could not complete travel-readiness research because a provider is unavailable."
        )
        return {
            "messages": [message],
            "current_agent": "readiness",
            "itinerary_components": {
                "readiness": {"messages": [message], "data": None}
            },
            "component_results": {"readiness": outcome.model_dump(mode="json")},
        }


@traceable(
    run_type="chain", name="restaurants_node", tags=["wanderlisted", "restaurants"]
)
async def restaurants_node(state: TravelAgentState, *, executor) -> dict:
    """Fan-out worker: run RestaurantsAgent as an independent graph node."""
    return await _run_parallel_agent(state, executor=executor, agent_name="restaurants")


@traceable(
    run_type="chain", name="activities_node", tags=["wanderlisted", "activities"]
)
async def activities_node(state: TravelAgentState, *, executor) -> dict:
    """Fan-out worker: run ActivitiesAgent as an independent graph node."""
    return await _run_parallel_agent(state, executor=executor, agent_name="activities")


@traceable(
    run_type="chain",
    name="transportation_node",
    tags=["wanderlisted", "transportation"],
)
async def transportation_node(state: TravelAgentState, *, executor) -> dict:
    """Build a typed route plan, or answer a narrow standalone route query."""
    components = state.get("itinerary_components", {})
    draft_data = components.get("draft_itinerary_structured")
    if not draft_data:
        return await _run_parallel_agent(
            state, executor=executor, agent_name="transportation"
        )

    try:
        draft = DraftItinerary.model_validate(draft_data)
    except Exception as exc:
        _log.warning(
            "Invalid draft itinerary; using standalone transport agent: %s", exc
        )
        return await _run_parallel_agent(
            state, executor=executor, agent_name="transportation"
        )

    async def _route_day(day) -> DayRoute:
        stop_locations = [stop.route_location() for stop in day.stops]
        try:
            result = await asyncio.to_thread(
                compute_day_route_data,
                stop_locations,
                day.start_location.route_location(),
                (day.end_location or day.start_location).route_location(),
                str(day.preferred_mode),
            )
        except Exception as exc:
            _log.warning("Route computation failed for day %s: %s", day.day_number, exc)
            return DayRoute(
                day_number=day.day_number,
                mode=day.preferred_mode,
                ordered_stops=day.stops,
                warning=f"Route computation unavailable: {type(exc).__name__}",
            )
        refs_by_location: dict[str, list[PlaceRef]] = {}
        for stop in day.stops:
            refs_by_location.setdefault(stop.route_location(), []).append(stop)
        ordered_refs = []
        for location in result["ordered_stops"]:
            matches = refs_by_location.get(location, [])
            if matches:
                ordered_refs.append(matches.pop(0))

        names_by_location = {
            day.start_location.route_location(): day.start_location.name,
            (day.end_location or day.start_location).route_location(): (
                day.end_location or day.start_location
            ).name,
            **{stop.route_location(): stop.name for stop in day.stops},
        }
        route_legs = [
            RouteLeg(
                from_place=names_by_location.get(
                    leg["from_location"], leg["from_location"]
                ),
                to_place=names_by_location.get(leg["to_location"], leg["to_location"]),
                mode=day.preferred_mode,
                distance_meters=leg["distance_meters"],
                duration_seconds=leg["duration_seconds"],
                route_leg_index=leg.get("route_leg_index"),
                instructions=leg["instructions"],
            )
            for leg in result["legs"]
        ]
        return DayRoute(
            day_number=day.day_number,
            mode=day.preferred_mode,
            ordered_stops=ordered_refs,
            legs=route_legs,
            total_distance_meters=result["total_distance_meters"],
            total_duration_seconds=result["total_duration_seconds"],
            warning=result["error"],
        )

    days = await asyncio.gather(*(_route_day(day) for day in draft.days))
    route_plan = RoutePlan(
        days=days,
        mobility_notes=draft.mobility_notes,
        warnings=[day.warning for day in days if day.warning],
    )
    route_json = route_plan.model_dump_json(indent=2)
    route_message = AIMessage(content=f"ROUTE_PLAN_JSON:\n{route_json}")
    return (
        await _run_parallel_agent(state, executor=executor, agent_name="transportation")
        if not draft.days
        else {
            "messages": [route_message],
            "current_agent": "transportation",
            "itinerary_components": {
                "transportation": {"messages": [route_message]},
                "route_plan_structured": route_plan.model_dump(),
                "completed_agents": components.get("completed_agents", [])
                + ["TransportationAgent"],
            },
        }
    )


@traceable(
    run_type="chain", name="draft_itinerary_node", tags=["wanderlisted", "draft"]
)
async def draft_itinerary_node(
    state: TravelAgentState,
    *,
    agent: ItineraryAgent | None = None,
    llm=None,
) -> dict:
    """Select provider source IDs, then resolve them to an immutable draft."""
    components = state.get("itinerary_components", {})

    def _component_text(key: str) -> str:
        return " ".join(
            _extract_text_content(message.content)
            for message in components.get(key, {}).get("messages", [])
            if isinstance(message, (AIMessage, ToolMessage)) and message.content
        )

    raw_evidence = "\n\n".join(
        f"[{key.upper()}]\n{text}"
        for key in ("hotels", "activities", "restaurants")
        if (text := _component_text(key))
    )
    try:
        request = TripRequest.model_validate(state.get("trip_request", {}))
        skeleton = TripSkeleton.model_validate(
            components.get("trip_skeleton_structured", {})
        )
        catalog = build_evidence_catalog(components, skeleton)
        selector = agent or ItineraryAgent(llm)
        draft = await selector.select_draft(
            ItinerarySelectionContext(
                request=request,
                skeleton=skeleton,
                catalog=catalog,
                feedback=state.get("human_feedback", ""),
                raw_evidence=raw_evidence,
            )
        )
    except Exception as exc:
        _log.warning("Typed itinerary selection failed: %s", exc)
        errors = (
            list(exc.errors)
            if isinstance(exc, ItineraryValidationError)
            else [f"{type(exc).__name__}: {exc}"]
        )
        message = AIMessage(
            content="Itinerary selection failed validation: " + "; ".join(errors)
        )
        outcome = ComponentResult(
            component="draft_itinerary",
            status=ComponentStatus.FAILED,
            message=_extract_text_content(message.content),
            error_category=ErrorCategory.VALIDATION,
            error_detail="; ".join(errors)[:500],
        )
        return {
            "messages": [message],
            "current_agent": "draft_itinerary:failed",
            "itinerary_components": {
                "draft_itinerary": {"messages": [message]},
                "draft_itinerary_structured": None,
            },
            "component_results": {"draft_itinerary": outcome.model_dump(mode="json")},
        }

    feedback = state.get("human_feedback", "").strip()
    prior_draft_data = components.get("draft_itinerary_structured")
    if feedback and prior_draft_data:
        prior_draft = DraftItinerary.model_validate(prior_draft_data)

        def _selection_signature(value: DraftItinerary) -> tuple:
            return (
                tuple(
                    (item.stay_sequence, item.rate_key)
                    for item in value.selected_accommodations
                ),
                tuple(
                    (
                        day.day_number,
                        tuple(stop.source_id for stop in day.stops),
                        str(day.preferred_mode),
                    )
                    for day in value.days
                ),
            )

        if _selection_signature(draft) == _selection_signature(prior_draft):
            message = AIMessage(
                content=(
                    "The requested edit could not be resolved from the existing "
                    "hotel and place catalog. Please choose an available stop or "
                    "authorize a new search."
                )
            )
            outcome = ComponentResult(
                component="draft_itinerary",
                status=ComponentStatus.NEEDS_USER_INPUT,
                message=_extract_text_content(message.content),
                missing_fields=["supported_catalog_edit"],
            )
            return {
                "messages": [message],
                "current_agent": "draft_itinerary:needs_user_input",
                "workflow_status": "needs_user_input",
                "pending_questions": [
                    "Which existing catalog stop should be changed, or should I run a new search?"
                ],
                "component_results": {
                    "draft_itinerary": outcome.model_dump(mode="json")
                },
            }

    draft_json = draft.model_dump_json(indent=2)
    draft_message = AIMessage(content=f"DRAFT_ITINERARY_JSON:\n{draft_json}")
    outcome = ComponentResult(
        component="draft_itinerary",
        status=ComponentStatus.COMPLETED,
        data=draft.model_dump(mode="json"),
        message="Provider-backed hotels and stops selected.",
        evidence_count=len(draft.selected_accommodations)
        + sum(len(day.stops) for day in draft.days),
    )
    return {
        "messages": [draft_message],
        "current_agent": "draft_itinerary",
        "human_feedback": "",
        "itinerary_components": {
            "draft_itinerary": {"messages": [draft_message]},
            "draft_itinerary_structured": draft.model_dump(mode="json"),
        },
        "component_results": {"draft_itinerary": outcome.model_dump(mode="json")},
    }


@traceable(run_type="chain", name="budget_node", tags=["wanderlisted", "budget"])
async def budget_node(state: TravelAgentState, *, agent: BudgetAgent) -> dict:
    """Run the fixed typed Budget pipeline from canonical graph artifacts."""
    components = state.get("itinerary_components", {})
    request = TripRequest.model_validate(state.get("trip_request", {}))
    skeleton_data = components.get("trip_skeleton_structured")
    draft_data = components.get("draft_itinerary_structured")
    skeleton = TripSkeleton.model_validate(skeleton_data) if skeleton_data else None
    draft = DraftItinerary.model_validate(draft_data) if draft_data else None
    prior_evidence = tuple(
        PriceEvidence.model_validate(item)
        for item in components.get("budget_evidence_structured", [])
    )
    prior_report = components.get("budget_structured", {})
    stored_rates = tuple(
        ConversionRateRecord.model_validate(item)
        for item in prior_report.get("conversion_rates", [])
    )
    try:
        run = await agent.run(
            BudgetContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                components=components,
                additional_evidence=prior_evidence,
                stored_rates=stored_rates,
            )
        )
    except Exception as exc:
        _log.warning("Budget pipeline failed: %s: %s", type(exc).__name__, exc)
        message = AIMessage(content="Budget calculation failed validation.")
        outcome = classify_component_result("budget", [], error=exc)
        return {
            "messages": [message],
            "current_agent": "budget:failed",
            "hitl_action": "",
            "itinerary_components": {
                "budget": {"messages": [message]},
                "budget_structured": None,
            },
            "component_results": {"budget": outcome.model_dump(mode="json")},
        }

    message = AIMessage(content=run.message)
    report = run.report.model_dump(mode="json")
    outcome = ComponentResult(
        component="budget",
        status=ComponentStatus.COMPLETED,
        data=report,
        message=run.message,
        missing_fields=[category.value for category in run.report.missing_categories],
        evidence_count=len(run.report.line_items),
        request_fingerprint=run.report.request_fingerprint,
    )
    completed_agents = list(components.get("completed_agents", []))
    if "BudgetAgent" not in completed_agents:
        completed_agents.append("BudgetAgent")
    return {
        "messages": [message],
        "current_agent": "budget",
        "hitl_action": "",
        "budget_adjustment_accepted": False,
        "itinerary_components": {
            "budget": {"messages": [message]},
            "budget_structured": report,
            "budget_evidence_structured": [
                item.model_dump(mode="json") for item in run.evidence
            ],
            "completed_agents": completed_agents,
        },
        "component_results": {"budget": outcome.model_dump(mode="json")},
    }


@traceable(run_type="chain", name="itinerary_node", tags=["wanderlisted", "itinerary"])
async def itinerary_node(
    state: TravelAgentState,
    *,
    agent: ItineraryAgent | None = None,
    executor=None,
) -> dict:
    """Compile canonical artifacts; no model may rewrite factual day-plan data."""
    # Compatibility for direct callers of the pre-typed node. Production graph
    # always injects ``agent`` and never registers a free-form executor.
    if agent is None and executor is not None:
        enriched = build_context_messages(state)
        result = await executor.ainvoke({"messages": enriched})
        new_msgs = result["messages"][len(enriched) :]
        components = state.get("itinerary_components", {})
        completed = list(components.get("completed_agents", []))
        if "ItineraryAgent" not in completed:
            completed.append("ItineraryAgent")
        return {
            "messages": new_msgs,
            "current_agent": "itinerary",
            "itinerary_components": {
                "itinerary": {"messages": new_msgs},
                "completed_agents": completed,
            },
        }

    components = state.get("itinerary_components", {})
    try:
        request = TripRequest.model_validate(state.get("trip_request", {}))
        skeleton = TripSkeleton.model_validate(
            components.get("trip_skeleton_structured", {})
        )
        draft = DraftItinerary.model_validate(
            components.get("draft_itinerary_structured", {})
        )
        route_data = components.get("route_plan_structured")
        route_plan = RoutePlan.model_validate(route_data) if route_data else None
        budget_data = components.get("budget_structured")
        budget = BudgetBreakdown.model_validate(budget_data) if budget_data else None
        readiness_data = components.get("readiness", {}).get("data") or components.get(
            "readiness_preflight", {}
        ).get("data")
        readiness = (
            TravelReadinessReport.model_validate(readiness_data)
            if readiness_data
            else None
        )
        compiler = agent or ItineraryAgent()
        run = compiler.compile(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=route_plan,
                budget=budget,
                readiness=readiness,
                request_revision=state.get("request_revision", 0),
            )
        )
    except Exception as exc:
        _log.warning("Typed itinerary compilation failed: %s", exc)
        errors = (
            list(exc.errors)
            if isinstance(exc, ItineraryValidationError)
            else [f"{type(exc).__name__}: {exc}"]
        )
        message = AIMessage(
            content="Itinerary compilation failed validation: " + "; ".join(errors)
        )
        outcome = ComponentResult(
            component="itinerary",
            status=ComponentStatus.FAILED,
            message=_extract_text_content(message.content),
            error_category=ErrorCategory.VALIDATION,
            error_detail="; ".join(errors)[:500],
        )
        return {
            "messages": [message],
            "current_agent": "itinerary:failed",
            "itinerary_components": {
                "itinerary": {"messages": [message]},
                "itinerary_structured": None,
            },
            "component_results": {"itinerary": outcome.model_dump(mode="json")},
        }

    message = AIMessage(content=run.message)
    plan = run.plan.model_dump(mode="json")
    completed = list(components.get("completed_agents", []))
    if "ItineraryAgent" not in completed:
        completed.append("ItineraryAgent")
    outcome_status = (
        ComponentStatus.COMPLETED
        if run.plan.coverage_status == "complete"
        else ComponentStatus.PARTIAL
    )
    outcome = ComponentResult(
        component="itinerary",
        status=outcome_status,
        data=plan,
        message="Typed itinerary compiled from canonical artifacts.",
        missing_fields=run.plan.missing_constraints,
        evidence_count=sum(
            len(block.activities) + (1 if block.restaurant else 0)
            for day in run.plan.days
            for block in day.time_blocks
        ),
        request_fingerprint=run.plan.artifact_fingerprint,
    )
    return {
        "messages": [message],
        "current_agent": "itinerary",
        "itinerary_components": {
            "itinerary": {"messages": [message]},
            "itinerary_structured": plan,
            "completed_agents": completed,
        },
        "component_results": {"itinerary": outcome.model_dump(mode="json")},
    }


@traceable(
    run_type="chain", name="render_handbook_node", tags=["wanderlisted", "render"]
)
async def render_handbook_node(
    state: TravelAgentState,
    *,
    llm=None,
) -> dict:
    """Validate current typed artifacts and render without model/provider calls."""
    components = state.get("itinerary_components", {})
    raw_plan = components.get("itinerary_structured")
    if not raw_plan:
        message = AIMessage(
            content=(
                "No validated itinerary data is available, so a handbook was not "
                "generated."
            )
        )
        outcome = ComponentResult(
            component="handbook",
            status=ComponentStatus.FAILED,
            message=_extract_text_content(message.content),
            error_category=ErrorCategory.VALIDATION,
            error_detail="itinerary_structured is missing",
        )
        return {
            "messages": [message],
            "current_agent": "render_handbook:failed",
            "workflow_status": "failed",
            "itinerary_components": {"handbook_structured": None},
            "component_results": {"handbook": outcome.model_dump(mode="json")},
        }

    try:
        request = TripRequest.model_validate(state.get("trip_request", {}))
        skeleton = TripSkeleton.model_validate(
            components.get("trip_skeleton_structured", {})
        )
        draft = DraftItinerary.model_validate(
            components.get("draft_itinerary_structured", {})
        )
        route_data = components.get("route_plan_structured")
        route_plan = RoutePlan.model_validate(route_data) if route_data else None
        budget_data = components.get("budget_structured")
        budget = BudgetBreakdown.model_validate(budget_data) if budget_data else None
        readiness_data = components.get("readiness", {}).get("data") or components.get(
            "readiness_preflight", {}
        ).get("data")
        readiness = (
            TravelReadinessReport.model_validate(readiness_data)
            if readiness_data
            else None
        )
        plan = ItineraryPlan.model_validate(raw_plan)
        expected_fingerprint = compute_artifact_fingerprint(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=route_plan,
                budget=budget,
                readiness=readiness,
                request_revision=state.get("request_revision", 0),
            )
        )
    except (TypeError, ValueError) as exc:
        message = AIMessage(
            content="Handbook generation failed typed-artifact validation."
        )
        outcome = ComponentResult(
            component="handbook",
            status=ComponentStatus.FAILED,
            message=_extract_text_content(message.content),
            error_category=ErrorCategory.VALIDATION,
            error_detail=str(exc)[:500],
        )
        return {
            "messages": [message],
            "current_agent": "render_handbook:failed",
            "workflow_status": "failed",
            "itinerary_components": {"handbook_structured": None},
            "component_results": {"handbook": outcome.model_dump(mode="json")},
        }

    if plan.artifact_fingerprint != expected_fingerprint:
        message = AIMessage(
            content=(
                "The itinerary is stale because its source artifacts changed. "
                "Recompile the itinerary before generating the handbook."
            )
        )
        stale = ComponentResult(
            component="itinerary",
            status=ComponentStatus.STALE,
            data=plan.model_dump(mode="json"),
            message=_extract_text_content(message.content),
            error_category=ErrorCategory.VALIDATION,
            error_detail="artifact fingerprint mismatch",
            request_fingerprint=plan.artifact_fingerprint,
        )
        handbook_outcome = ComponentResult(
            component="handbook",
            status=ComponentStatus.STALE,
            message=_extract_text_content(message.content),
            error_category=ErrorCategory.VALIDATION,
            error_detail="artifact fingerprint mismatch",
            request_fingerprint=expected_fingerprint,
        )
        return {
            "messages": [message],
            "current_agent": "render_handbook:stale",
            "workflow_status": "stale",
            "itinerary_components": {"handbook_structured": None},
            "component_results": {
                "itinerary": stale.model_dump(mode="json"),
                "handbook": handbook_outcome.model_dump(mode="json"),
            },
        }

    try:
        renderer = HandbookRenderer()
        handbook = renderer.build_handbook(state)
        paths = await asyncio.to_thread(renderer.write_outputs, handbook)
    except (OSError, TypeError, ValueError) as exc:
        message = AIMessage(content="Handbook rendering failed.")
        outcome = ComponentResult(
            component="handbook",
            status=ComponentStatus.FAILED,
            message=_extract_text_content(message.content),
            error_category=ErrorCategory.INTERNAL,
            error_detail=str(exc)[:500],
            request_fingerprint=expected_fingerprint,
        )
        return {
            "messages": [message],
            "current_agent": "render_handbook:failed",
            "workflow_status": "failed",
            "itinerary_components": {"handbook_structured": None},
            "component_results": {"handbook": outcome.model_dump(mode="json")},
        }

    path_strings = {name: str(path) for name, path in paths.items()}
    status = (
        ComponentStatus.COMPLETED
        if plan.coverage_status == "complete"
        else ComponentStatus.PARTIAL
    )
    outcome = ComponentResult(
        component="handbook",
        status=status,
        data=handbook.model_dump(mode="json"),
        message="Deterministic handbook rendered from validated typed artifacts.",
        missing_fields=list(plan.missing_constraints),
        evidence_count=sum(
            len(block.activities) + (1 if block.restaurant else 0)
            for day in plan.days
            for block in day.time_blocks
        ),
        request_fingerprint=expected_fingerprint,
    )
    qualification = (
        " Feasibility warnings and unscheduled stops are included."
        if status == ComponentStatus.PARTIAL
        else ""
    )
    message = AIMessage(
        content=(
            "📘 **Travel Handbook Generated!**\n\n"
            "The handbook was compiled from the validated itinerary artifacts."
            f"{qualification}\n\n"
            f"- 📄 HTML: `{path_strings.get('html', '')}`\n"
            f"- 📝 Markdown: `{path_strings.get('markdown', '')}`\n"
            f"- 📊 JSON: `{path_strings.get('json', '')}`"
        )
    )
    return {
        "messages": [message],
        "current_agent": "render_handbook",
        "workflow_status": (
            "completed" if status == ComponentStatus.COMPLETED else "partial"
        ),
        "handbook_paths": path_strings,
        "itinerary_components": {
            "handbook_structured": handbook.model_dump(mode="json")
        },
        "component_results": {"handbook": outcome.model_dump(mode="json")},
    }


@traceable(
    run_type="chain", name="synthesize_node", tags=["wanderlisted", "synthesize"]
)
async def synthesize_node(state: TravelAgentState, *, llm) -> dict:
    """Answer follow-up questions from existing specialist data without re-running tools."""
    enriched = build_context_messages(state)
    response = await llm.ainvoke(
        [
            SystemMessage(content=SYNTHESIZE_SYSTEM_PROMPT),
            *enriched,
        ]
    )
    return {
        "messages": [response],
        "current_agent": "synthesize",
    }


# ── Routing functions (module-level, testable) ────────────────────────────


def route_after_triage(state: TravelAgentState) -> str:
    """Route shallow queries directly and all planning turns through intake.

    A target_agent still passes through intake so required specialist inputs
    cannot be bypassed.
    """
    if state.get("target_agent"):
        return "intake"
    if state.get("pending_questions"):
        return "intake"
    agent = state.get("current_agent", "")
    if agent == "triage:shallow":
        return "shallow_reply"
    return "intake"


def route_after_intake(state: TravelAgentState) -> str:
    """Stop for clarification or continue to specialist routing."""
    if state.get("workflow_status") == "ready":
        return "supervisor"
    return END


def route_after_component_gate(state: TravelAgentState) -> str:
    """Continue only when requested discovery components actually completed."""
    if state.get("workflow_status") != "planning":
        return END
    return _route_to_dependent_stage(state)


def _route_to_dependent_stage(state: TravelAgentState) -> str:
    components = state.get("itinerary_components", {})
    routing = components.get("routing", [])
    if (
        "HotelsAgent" in routing
        or DEPENDENT_TRANSPORTATION_AGENT in routing
        or "ItineraryAgent" in routing
    ):
        return "trip_skeleton"
    if "BudgetAgent" in routing:
        return "budget"
    return END


def _needs_safety_preflight(state: TravelAgentState) -> bool:
    routing = state.get("itinerary_components", {}).get("routing", [])
    if "TravelReadinessAgent" not in routing:
        return False
    request = TripRequest.model_validate(state.get("trip_request", {}))
    question = _latest_human_question(state)
    required = (
        request.scope == RequestScope.FULL_ITINERARY
        or ReadinessTopic.SAFETY in request.readiness_topics
        or any(
            word in question.lower() for word in ("safe", "safety", "advisory", "risk")
        )
    )
    if not required:
        return False
    expected = readiness_request_fingerprint(
        request,
        requested_topics(question, request) | {ReadinessTopic.SAFETY},
    )
    outcomes = state.get("component_results", {})
    return not any(
        outcomes.get(name, {}).get("status") == ComponentStatus.COMPLETED
        and outcomes.get(name, {}).get("request_fingerprint") == expected
        for name in ("readiness_preflight", "readiness")
    )


def _readiness_result_is_current(state: TravelAgentState) -> bool:
    request = TripRequest.model_validate(state.get("trip_request", {}))
    topics = requested_topics(_latest_human_question(state), request)
    expected = readiness_request_fingerprint(request, topics)
    outcome = state.get("component_results", {}).get("readiness", {})
    return (
        outcome.get("status") == ComponentStatus.COMPLETED
        and outcome.get("request_fingerprint") == expected
    )


def route_after_supervisor(state: TravelAgentState):
    """Fan-out via Send() to each requested parallel agent, or route sequentially.

    Returns a list of Send() objects — one per requested parallel agent — so
    each agent runs as an independent graph node with its own checkpoint,
    trace, and retry scope.  Falls back to a string destination for the
    sequential-only and synthesize cases.
    """
    components = state.get("itinerary_components", {})
    routing = components.get("routing", [])

    if not routing:
        # No agents requested — check if follow-up synthesis is needed
        has_data = any(k in components for k in DATA_KEYS)
        if has_data:
            return "synthesize"
        return END

    if _needs_safety_preflight(state):
        return "readiness_preflight"

    # Readiness must finish before discovery so downstream specialists receive
    # grounded planning constraints instead of running from the same stale state.
    if "TravelReadinessAgent" in routing and not _readiness_result_is_current(state):
        return "readiness"

    # Fan-out: one Send per requested discovery agent. LangGraph runs them
    # concurrently and fans-in automatically before safety_review fires.
    parallel_requested = [
        agent
        for agent in routing
        if agent in PARALLEL_AGENTS
        and not (
            agent == "TravelReadinessAgent" and _readiness_result_is_current(state)
        )
    ]
    if parallel_requested:
        return [Send(AGENT_TO_NODE[a], state) for a in parallel_requested]

    # Only dependent/sequential agents requested.
    if "HotelsAgent" in routing:
        return "trip_skeleton"
    if DEPENDENT_TRANSPORTATION_AGENT in routing:
        return "transportation"
    if "BudgetAgent" in routing:
        return "budget"
    if "ItineraryAgent" in routing:
        return "itinerary"

    return END


def route_after_readiness_preflight(state: TravelAgentState) -> str:
    """Fail closed when official advisory evidence could not be collected."""
    outcome = state.get("component_results", {}).get("readiness_preflight", {})
    if outcome.get("status") == ComponentStatus.COMPLETED:
        return "safety_review"
    return END


def route_after_safety_review(state: TravelAgentState):
    """After acknowledgement, dispatch discovery without repeating preflight."""
    if state.get("hitl_action") == "rejected":
        return END

    components = state.get("itinerary_components", {})
    routing = components.get("routing", [])
    request = TripRequest.model_validate(state.get("trip_request", {}))
    readiness_details_needed = request.scope == RequestScope.FULL_ITINERARY or any(
        topic != ReadinessTopic.SAFETY for topic in request.readiness_topics
    )
    if readiness_details_needed and (
        state.get("component_results", {}).get("readiness", {}).get("status")
        != ComponentStatus.COMPLETED
        or "readiness_preflight" in components
    ):
        return "readiness"
    parallel_requested = [
        agent
        for agent in routing
        if agent in PARALLEL_AGENTS and agent != "TravelReadinessAgent"
    ]
    if parallel_requested:
        return [Send(AGENT_TO_NODE[agent], state) for agent in parallel_requested]
    return _route_to_dependent_stage(state)


def route_after_readiness(state: TravelAgentState):
    """Dispatch discovery only after grounded readiness details are available."""
    outcome = state.get("component_results", {}).get("readiness", {})
    if outcome.get("status") != ComponentStatus.COMPLETED:
        return "component_gate"

    routing = state.get("itinerary_components", {}).get("routing", [])
    parallel_requested = [
        agent
        for agent in routing
        if agent in PARALLEL_AGENTS and agent != "TravelReadinessAgent"
    ]
    if parallel_requested:
        return [Send(AGENT_TO_NODE[agent], state) for agent in parallel_requested]
    return "component_gate"


def route_after_trip_skeleton(state: TravelAgentState):
    """Fan out exact city stays to Hotels or continue dependent planning."""
    if state.get("workflow_status") != "skeleton_ready":
        return END
    components = state.get("itinerary_components", {})
    routing = components.get("routing", [])
    if "HotelsAgent" in routing:
        skeleton = TripSkeleton.model_validate(
            components.get("trip_skeleton_structured", {})
        )
        return [
            Send(
                "hotel_stay",
                {
                    **state,
                    "active_hotel_stay": stay.model_dump(mode="json"),
                },
            )
            for stay in skeleton.stays
        ]
    if DEPENDENT_TRANSPORTATION_AGENT in routing or "ItineraryAgent" in routing:
        return "draft_itinerary"
    if "BudgetAgent" in routing:
        return "budget"
    return END


def route_after_hotel_gate(state: TravelAgentState) -> str:
    """Continue only after every exact city stay produced hotel inventory."""
    if state.get("workflow_status") != "planning":
        return END
    routing = state.get("itinerary_components", {}).get("routing", [])
    if DEPENDENT_TRANSPORTATION_AGENT in routing or "ItineraryAgent" in routing:
        return "draft_itinerary"
    if "BudgetAgent" in routing:
        return "budget"
    return END


def route_after_draft_itinerary(state: TravelAgentState) -> str:
    """Route a selected draft through transportation, budget, or final assembly."""
    outcome = state.get("component_results", {}).get("draft_itinerary", {})
    if outcome and outcome.get("status") != ComponentStatus.COMPLETED:
        return END
    components = state.get("itinerary_components", {})
    routing = components.get("routing", [])

    if DEPENDENT_TRANSPORTATION_AGENT in routing:
        return "transportation"
    if "BudgetAgent" in routing:
        return "budget"
    if "ItineraryAgent" in routing:
        return "itinerary"
    return END


def route_after_transportation(state: TravelAgentState) -> str:
    """Route after transportation: continue to budget or itinerary when requested."""
    components = state.get("itinerary_components", {})
    routing = components.get("routing", [])

    if "BudgetAgent" in routing:
        return "budget"
    if "ItineraryAgent" in routing:
        return "itinerary"
    return END


def route_after_budget(state: TravelAgentState) -> str:
    """Route after budget: go to budget_review HITL gate."""
    return "budget_review"


def route_after_budget_review(state: TravelAgentState) -> str:
    """Route target edits to local recompute; never repeat discovery."""
    if state.get("hitl_action") == "adjust_target":
        return "budget"
    if state.get("hitl_action") in {"cancel", "rejected"}:
        return END

    components = state.get("itinerary_components", {})
    routing = components.get("routing", [])

    if "ItineraryAgent" in routing:
        return "itinerary"
    return END


def route_after_itinerary(state: TravelAgentState) -> str:
    """Only a validated typed plan reaches review and handbook rendering."""
    outcome = state.get("component_results", {}).get("itinerary", {})
    if outcome.get("status") in {
        ComponentStatus.COMPLETED,
        ComponentStatus.PARTIAL,
    }:
        return "human_review"
    return END


def route_after_human_review(state: TravelAgentState) -> str:
    """Apply edits through selection/routing; never claim unperformed changes."""
    if state.get("hitl_action") in {"rejected", "needs_clarification"}:
        return END
    if state.get("hitl_action") == "edited":
        return "draft_itinerary"
    return "render_handbook"


# ── Graph builder (thin wiring — all logic lives in module-level functions) ──


def create_multiagent_travel_graph(checkpointer=None):
    """Create a LangGraph with supervisor, parallel specialist dispatch, and sequential finishers.

    Uses a three-tier model pyramid for TPM / cost optimization:
        - ``llm`` (reasoning): gpt-5.4 (1M TPM) — complex multi-source
          synthesis agents (Destination, Itinerary).
        - ``llm_fast`` (fast): gpt-5.4-mini (1M TPM) — worker agents that call
          one API and format structured results.
        - ``llm_utility`` (utility): gpt-5.4-nano (1M TPM) — triage, supervisor
          routing, shallow replies, rendering, synthesis.

    All gpt-5.4 family models are reasoning models.  The LLM factory enables
    the Responses API and sets per-tier reasoning_effort (medium/low/low) to
    ensure tool calling works correctly (tool calling is NOT supported in
    Chat Completions with reasoning: none on gpt-5.4 models).
    """

    llm = get_llm(tier="reasoning")
    llm_fast = get_llm(tier="fast")
    llm_utility = get_llm(tier="utility")

    # --- agents & executors ---------------------------------------------------
    _supervisor_agent = SupervisorAgent(llm_utility)  # routing only — utility tier

    # Per-agent tier assignment: classify by task complexity, not agent name.
    # reasoning (gpt-5.4, 1 M TPM): deep multi-source synthesis with tool calling
    # fast (gpt-5.4-mini, 1 M TPM): API wrappers that call ONE service and format results
    # utility (gpt-5.4-nano, 1 M TPM): routing, extraction, rendering, shallow replies
    _AGENT_TIERS = {
        "FlightsAgent": llm_fast,  # Duffel API call + format
        "HotelsAgent": llm_fast,  # Hotelbeds API call + format
        "RestaurantsAgent": llm_fast,  # Google Maps API call + format
        "ActivitiesAgent": llm_fast,  # Google Maps API call + format
        "TransportationAgent": llm_fast,  # Google Maps API call + format
    }

    agent_classes = {
        "FlightsAgent": FlightsAgent,
        "HotelsAgent": HotelsAgent,
        "RestaurantsAgent": RestaurantsAgent,
        "ActivitiesAgent": ActivitiesAgent,
        "TransportationAgent": TransportationAgent,
    }

    _executors = {}
    for name, cls in agent_classes.items():
        model = _AGENT_TIERS[name]
        agent = cls(model)
        _executors[name] = create_agent(
            model=model,
            tools=agent.tools,
            system_prompt=agent.system_prompt,
        )

    # Readiness is a fixed Tavily + Open-Meteo pipeline, not a ReAct loop.
    _readiness_agent = TravelReadinessAgent(llm)
    # Budget is a typed extraction + deterministic arithmetic pipeline.
    _budget_agent = BudgetAgent(llm_utility)
    # Itinerary uses one bounded selection call, then a deterministic compiler.
    _itinerary_agent = ItineraryAgent(llm)

    # --- graph wiring ---------------------------------------------------------

    builder = StateGraph(TravelAgentState)

    # Nodes — thin wrappers that inject dependencies into module-level functions
    #
    # Utility tier (gpt-5.4-nano): triage, shallow_reply, supervisor, render_handbook, synthesize
    # Fast tier (gpt-5.4-mini): discovery workers plus standalone transportation
    # Reasoning tier (gpt-5.4): readiness synthesis, draft selection, final itinerary
    builder.add_node("triage", functools.partial(triage_node, llm=llm_utility))
    builder.add_node("intake", functools.partial(intake_node, llm=llm_utility))
    builder.add_node(
        "shallow_reply", functools.partial(shallow_reply_node, llm=llm_utility)
    )
    builder.add_node(
        "supervisor",
        functools.partial(supervisor_node, supervisor_agent=_supervisor_agent),
    )
    # Initial Send() discovery workers — Hotels runs later from TripSkeleton.
    builder.add_node(
        "flights", functools.partial(flights_node, executor=_executors["FlightsAgent"])
    )
    builder.add_node(
        "hotel_stay",
        functools.partial(hotel_stay_node, executor=_executors["HotelsAgent"]),
    )
    builder.add_node("hotel_fan_in", hotel_fan_in_node)
    builder.add_node(
        "readiness_preflight",
        functools.partial(readiness_preflight_node, executor=_readiness_agent),
    )
    builder.add_node(
        "readiness",
        functools.partial(readiness_node, executor=_readiness_agent),
    )
    builder.add_node(
        "restaurants",
        functools.partial(restaurants_node, executor=_executors["RestaurantsAgent"]),
    )
    builder.add_node(
        "activities",
        functools.partial(activities_node, executor=_executors["ActivitiesAgent"]),
    )
    builder.add_node(
        "transportation",
        functools.partial(
            transportation_node, executor=_executors["TransportationAgent"]
        ),
    )
    builder.add_node("safety_review", safety_review_node)
    builder.add_node(
        "component_gate",
        functools.partial(
            component_gate_node,
            eligible_components={
                "flights",
                "readiness",
                "restaurants",
                "activities",
            },
        ),
    )
    builder.add_node(
        "hotel_gate",
        functools.partial(
            component_gate_node,
            eligible_components={"hotels"},
        ),
    )
    builder.add_node("trip_skeleton", trip_skeleton_node)
    builder.add_node(
        "draft_itinerary",
        functools.partial(draft_itinerary_node, agent=_itinerary_agent),
    )
    builder.add_node(
        "budget",
        functools.partial(budget_node, agent=_budget_agent),
    )
    builder.add_node("budget_review", budget_review_node)
    builder.add_node(
        "itinerary",
        functools.partial(itinerary_node, agent=_itinerary_agent),
    )
    builder.add_node("human_review", human_review_node)
    builder.add_node(
        "render_handbook", functools.partial(render_handbook_node, llm=llm_utility)
    )
    builder.add_node("synthesize", functools.partial(synthesize_node, llm=llm_utility))

    # START -> triage
    builder.add_edge(START, "triage")

    # triage -> shallow_reply | intake | supervisor (developer target override)
    builder.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "shallow_reply": "shallow_reply",
            "intake": "intake",
            "supervisor": "supervisor",
        },
    )

    # intake -> supervisor when complete, otherwise end this conversational turn
    builder.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "supervisor": "supervisor",
            END: END,
        },
    )

    # shallow_reply always ends
    builder.add_edge("shallow_reply", END)

    # supervisor -> Send() fan-out to parallel agents | sequential | synthesize | END
    # When route_after_supervisor returns [Send("flights", state), Send("hotels", state), ...],
    # LangGraph dispatches each worker independently.  All workers fan-in to
    # safety_review once every dispatched instance has completed.
    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        [
            "flights",
            "hotel_stay",
            "readiness_preflight",
            "readiness",
            "restaurants",
            "activities",
            "trip_skeleton",
            "transportation",
            "budget",
            "itinerary",
            "synthesize",
            END,
        ],
    )

    # Safety preflight is a separate checkpoint so interrupt resume cannot
    # repeat provider calls.
    builder.add_conditional_edges(
        "readiness_preflight",
        route_after_readiness_preflight,
        {
            "safety_review": "safety_review",
            END: END,
        },
    )

    # safety_review dispatches discovery only after acknowledgement.
    builder.add_conditional_edges(
        "safety_review",
        route_after_safety_review,
        [
            "flights",
            "readiness",
            "restaurants",
            "activities",
            "trip_skeleton",
            "budget",
            END,
        ],
    )

    # Readiness completes before discovery and dispatches the remaining workers
    # with its grounded planning constraints in their input state.
    builder.add_conditional_edges(
        "readiness",
        route_after_readiness,
        [
            "flights",
            "restaurants",
            "activities",
            "component_gate",
        ],
    )

    # Fan-in: every discovery worker → component completion gate.
    # LangGraph waits for ALL Send() instances before evaluating outcomes.
    for _worker in [
        "flights",
        "restaurants",
        "activities",
    ]:
        builder.add_edge(_worker, "component_gate")

    # Never draft or render a plan from clarification/error/no-inventory prose.
    builder.add_conditional_edges(
        "component_gate",
        route_after_component_gate,
        {
            "trip_skeleton": "trip_skeleton",
            "budget": "budget",
            END: END,
        },
    )

    # Exact dates/night allocation -> one Hotelbeds worker per city stay.
    builder.add_conditional_edges(
        "trip_skeleton",
        route_after_trip_skeleton,
        [
            "hotel_stay",
            "draft_itinerary",
            "budget",
            END,
        ],
    )
    builder.add_edge("hotel_stay", "hotel_fan_in")
    builder.add_edge("hotel_fan_in", "hotel_gate")
    builder.add_conditional_edges(
        "hotel_gate",
        route_after_hotel_gate,
        {
            "draft_itinerary": "draft_itinerary",
            "budget": "budget",
            END: END,
        },
    )

    # Draft selection fixes the exact hotel and stops before route computation.
    builder.add_conditional_edges(
        "draft_itinerary",
        route_after_draft_itinerary,
        {
            "transportation": "transportation",
            "budget": "budget",
            "itinerary": "itinerary",
            END: END,
        },
    )

    # Transportation deterministically routes the selected draft once.
    builder.add_conditional_edges(
        "transportation",
        route_after_transportation,
        {
            "budget": "budget",
            "itinerary": "itinerary",
            END: END,
        },
    )

    # budget -> budget_review (always)
    builder.add_conditional_edges(
        "budget",
        route_after_budget,
        {
            "budget_review": "budget_review",
        },
    )

    # budget_review -> itinerary | END
    builder.add_conditional_edges(
        "budget_review",
        route_after_budget_review,
        {"budget": "budget", "itinerary": "itinerary", END: END},
    )

    # Only a validated typed itinerary can proceed to review.
    builder.add_conditional_edges(
        "itinerary",
        route_after_itinerary,
        {"human_review": "human_review", END: END},
    )

    # human_review -> render_handbook | END
    builder.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "draft_itinerary": "draft_itinerary",
            "render_handbook": "render_handbook",
            END: END,
        },
    )

    builder.add_edge("render_handbook", END)
    builder.add_edge("synthesize", END)

    return builder.compile(checkpointer=checkpointer)


# Module-level graph for LangGraph Studio / langgraph dev
graph = create_multiagent_travel_graph()


if __name__ == "__main__":
    print("Creating multi-agent graph...")
    g = create_multiagent_travel_graph()
    print(f"Graph: {len(g.nodes)} nodes")
    result = g.invoke(
        {
            "messages": [HumanMessage("Plan my Tokyo trip")],
            "session_id": "test_123",
        },
    )
    print(f"Result: Current agent = {result.get('current_agent')}")
    print(f"Messages: {len(result['messages'])} messages in conversation")
