"""Stage 4: Multi-Agent Supervisor Graph using LangGraph.

Parallel multi-agent architecture using Send() fan-out: the supervisor
decides which specialist agents are needed and dispatches each one as an
independent graph node via Send().  This gives per-agent checkpointing,
individual retry on failure, dedicated traces in LangGraph Studio, and
native per-agent streaming.  Dependent agents (Budget, Itinerary) run
sequentially afterward since they need the earlier results.

Flow (Send() fan-out → fan-in → sequential phase → HITL review → render):
    START → triage → supervisor ──Send──┬── flights ────┐
                                        ├── hotels ─────┤
                                        ├── destination ┤
                                        ├── restaurants ─┤ → safety_review (HITL)
                                        ├── activities ──┤   → budget → budget_review (HITL)
                                        └── transportation┘     → itinerary → human_review (HITL)
                                                                     → render_handbook → END

HITL gates:
    - safety_review: interrupts when advisory is "do not travel" / "red"
    - budget_review: interrupts when budget overspent by >$500
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
import os
import re
from typing import Any

import functools

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Send
from langsmith import traceable

from custom_logging import AppLogger
from src.agent.llm import get_llm
from src.agent.state import TravelAgentState
from src.agent.prompts import (
    SYNTHESIZE_SYSTEM_PROMPT,
    TRIAGE_SYSTEM_PROMPT,
)
from src.models import BudgetBreakdown
from src.models.itinerary import (
    CultureGuide,
    DayPlan,
    FlightOption,
    HotelOption,
    PackingItem,
    SafetyInfo,
    TripHandbook,
)
from src.agent.renderer import HandbookRenderer
from src.agent.agents import (
    SupervisorAgent,
    FlightsAgent,
    HotelsAgent,
    DestinationAgent,
    BudgetAgent,
    RestaurantsAgent,
    ActivitiesAgent,
    TransportationAgent,
    ItineraryAgent,
)

import config as app_config

# ── Routing lists from config (with sensible defaults) ────────────────────
_routing_cfg = app_config.get("routing") or {}

PARALLEL_AGENTS = _routing_cfg.get(
    "parallel_agents",
    [
        "FlightsAgent",
        "HotelsAgent",
        "DestinationAgent",
        "RestaurantsAgent",
        "ActivitiesAgent",
        "TransportationAgent",
    ],
)
SEQUENTIAL_AGENTS = _routing_cfg.get(
    "sequential_agents",
    [
        "BudgetAgent",
        "ItineraryAgent",
    ],
)

ALL_AGENTS = PARALLEL_AGENTS + SEQUENTIAL_AGENTS

AGENT_TO_NODE = {
    "FlightsAgent": "flights",
    "HotelsAgent": "hotels",
    "DestinationAgent": "destination",
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
    return "USER PROFILE:\n" + "\n".join(parts)


def build_context_messages(state: TravelAgentState) -> list:
    """Build message list enriched with results from prior agents and user profile.

    Checks for data keys directly rather than the per-invocation
    completed_agents list, so context is available both within a single
    run AND across follow-up turns.
    """
    components = state.get("itinerary_components", {})
    label_map = {
        "flights": "Flights results",
        "hotels": "Hotels results",
        "destination": "Destination info",
        "budget": "Budget results",
        "restaurants": "Restaurants results",
        "activities": "Activities results",
        "transportation": "Transportation results",
        "itinerary": "Itinerary results",
    }

    parts = []
    for key, label in label_map.items():
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

    # Inject user profile
    profile = build_user_profile_context(state)
    if profile:
        msgs.insert(0, SystemMessage(content=profile))

    if parts:
        context = (
            "Here is what specialist agents found. "
            "Use this context to give a more informed answer.\n\n" + "\n\n".join(parts)
        )
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

    Checks destination agent results for dangerous advisory levels.
    If dangerous, pauses execution so the user can acknowledge the risk
    or cancel the trip.

    Disabled when hitl.safety_review = false (webapp mode).
    """
    if not is_hitl_enabled("safety_review"):
        return {"current_agent": "safety_review"}

    components = state.get("itinerary_components", {})
    destination_data = components.get("destination", {})

    # Extract safety/advisory text from destination agent output (messages + tool results)
    safety_text = ""
    for m in destination_data.get("messages", []):
        if isinstance(m, (AIMessage, ToolMessage)) and m.content:
            content = _extract_text_content(m.content)
            safety_text += content.lower() + "\n"

    # Check for dangerous advisory levels — both structured patterns and
    # natural language phrases that destination/web tools may return
    danger_keywords = [
        "do not travel",
        "level 4",
        "advisory level: red",
        "reconsider travel",
        "level 3",
        "avoid all travel",
        "avoid non-essential travel",
        "extreme risk",
        "war zone",
        "armed conflict",
        "active conflict",
    ]
    is_dangerous = any(kw in safety_text for kw in danger_keywords)

    if is_dangerous and not state.get("safety_acknowledged"):
        # Extract the most relevant safety snippet for the user
        safety_snippet = ""
        for kw in danger_keywords:
            idx = safety_text.find(kw)
            if idx >= 0:
                start = max(0, idx - 100)
                end = min(len(safety_text), idx + 200)
                safety_snippet = safety_text[start:end].strip()
                break

        raw_decision = interrupt(
            {
                "type": "safety_warning",
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

        return {
            "current_agent": "safety_review",
            "safety_acknowledged": True,
            "hitl_action": "approved",
        }

    # No safety concern — pass through
    return {"current_agent": "safety_review"}


async def budget_review_node(state: TravelAgentState) -> dict:
    """HITL gate: interrupt when estimated budget exceeds target by >$500.

    Checks budget_structured for overspend and offers adjustment options.

    Disabled when hitl.budget_review = false (webapp mode).
    """
    if not is_hitl_enabled("budget_review"):
        return {"current_agent": "budget_review"}

    components = state.get("itinerary_components", {})
    budget_data = components.get("budget_structured", {})

    if not budget_data:
        return {"current_agent": "budget_review"}

    total_estimated = budget_data.get("total", 0)

    # Get target from structured extraction (BudgetBreakdown.target_budget)
    target_budget = budget_data.get("target_budget", 0)

    # Fallback: try to parse target from user messages if extraction missed it
    if not target_budget:
        for m in state.get("messages", []):
            if isinstance(m, HumanMessage) and m.content:
                text = _extract_text_content(m.content)
                # Match patterns like "$2000", "budget 2000", "budget of $3,000"
                match = re.search(
                    r"budget[:\s]*(?:of\s*)?\$?([\d,]+)", text, re.IGNORECASE
                )
                if match:
                    try:
                        target_budget = float(match.group(1).replace(",", ""))
                    except ValueError:
                        pass
                    break

    if not target_budget:
        # No explicit target — skip review
        return {"current_agent": "budget_review"}

    overspend = total_estimated - target_budget
    if overspend > 500 and not state.get("budget_adjustment_accepted"):
        raw_decision = interrupt(
            {
                "type": "budget_warning",
                "message": (
                    f"💰 BUDGET ALERT: Your estimated trip cost (${total_estimated:,.0f}) "
                    f"exceeds your target budget (${target_budget:,.0f}) by ${overspend:,.0f}."
                ),
                "estimated_total": total_estimated,
                "target_budget": target_budget,
                "overspend": overspend,
                "suggestions": [
                    "Switch to budget hotels to save ~20%",
                    "Reduce trip by 1-2 days",
                    "Choose economy flights",
                    "Cut optional activities",
                ],
                "action_required": (
                    "Respond with true to proceed as-is, "
                    "or provide feedback text to adjust."
                ),
            }
        )
        decision = _normalize_hitl_decision(raw_decision)

        if not decision.get("approved", False):
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "🔄 Budget adjustment requested. Please provide updated "
                            "budget preferences and I'll re-plan accordingly."
                        )
                    )
                ],
                "current_agent": "budget_review",
                "hitl_action": "rejected",
                "human_feedback": decision.get("feedback", ""),
            }

        feedback = decision.get("feedback", "")
        return {
            "current_agent": "budget_review",
            "budget_adjustment_accepted": True,
            "hitl_action": "approved",
            "human_feedback": feedback,
        }

    return {"current_agent": "budget_review"}


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
    if "destination" in components:
        summary_parts.append("🗺️ Destination info: found")
    if "transportation" in components:
        summary_parts.append("🚃 Transportation: found")
    if "budget" in components:
        summary_parts.append("💰 Budget: calculated")
    if "itinerary" in components:
        summary_parts.append("📅 Itinerary: assembled")

    itinerary_preview = ""
    for m in itinerary_data.get("messages", []):
        if isinstance(m, AIMessage) and m.content:
            itinerary_preview += _extract_text_content(m.content)[:2000]
            break

    raw_decision = interrupt(
        {
            "type": "itinerary_review",
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
        return {
            "messages": [
                AIMessage(
                    content=f"📝 Noted your feedback: {feedback}. Generating handbook with adjustments."
                )
            ],
            "current_agent": "human_review",
            "hitl_action": "edited",
            "human_feedback": feedback,
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
            SystemMessage(
                content=(
                    "You are a friendly travel planning assistant called Wanderlisted. "
                    "Answer the user's casual message briefly. If they seem to want "
                    "travel planning help, invite them to ask about destinations, "
                    "flights, hotels, activities, or budgets."
                ),
            ),
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
        "destination": "DestinationAgent: destination / weather / safety info",
        "budget": "BudgetAgent: budget breakdown",
        "restaurants": "RestaurantsAgent: restaurant recommendations",
        "activities": "ActivitiesAgent: activity and attraction results",
        "transportation": "TransportationAgent: transport and route info",
        "itinerary": "ItineraryAgent: assembled itinerary",
    }
    for key, desc in label_map.items():
        if key in components:
            data_parts.append(f"- {desc} already collected")

    existing_summary = ""
    if data_parts:
        existing_summary = (
            "DATA ALREADY COLLECTED in this conversation (do NOT re-run "
            "these agents unless the user explicitly asks for new data):\n"
            + "\n".join(data_parts)
            + "\n\nIf the user's request can be answered from this existing "
            "data, return agents: [] so the synthesizer handles it."
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
    decision = await supervisor_agent.aget_routing_decision(
        _extract_text_content(last_message.content),
        existing_summary,
    )

    # Ensure ItineraryAgent is always included when BudgetAgent is routed
    # (budget → itinerary → render_handbook is the required pipeline)
    if "BudgetAgent" in decision.agents and "ItineraryAgent" not in decision.agents:
        decision.agents.append("ItineraryAgent")

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


# ── Individual parallel worker nodes (Send() fan-out) ────────────────────
#
# Each function is an independent LangGraph node.  The supervisor fans out
# to them via [Send("node_name", state), ...] from route_after_supervisor.
# LangGraph automatically fans-in (waits for all) before safety_review runs.
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
    """Execute a parallel agent with error handling.

    If the agent fails (e.g. external API down), log the error and return a
    graceful degradation message instead of crashing the whole graph.
    """
    enriched = build_context_messages(state)
    try:
        result = await executor.ainvoke({"messages": enriched})
        new_msgs = result["messages"][len(enriched) :]
        return {
            "messages": new_msgs,
            "current_agent": agent_name,
            "itinerary_components": {agent_name: result},
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
                f"The rest of your itinerary will still be generated."
            ),
        )
        return {
            "messages": [error_msg],
            "current_agent": agent_name,
            "itinerary_components": {agent_name: {"error": str(exc)}},
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
    run_type="chain", name="destination_node", tags=["wanderlisted", "destination"]
)
async def destination_node(state: TravelAgentState, *, executor) -> dict:
    """Fan-out worker: run DestinationAgent as an independent graph node."""
    return await _run_parallel_agent(state, executor=executor, agent_name="destination")


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
    """Fan-out worker: run TransportationAgent as an independent graph node."""
    return await _run_parallel_agent(
        state, executor=executor, agent_name="transportation"
    )


@traceable(run_type="chain", name="budget_node", tags=["wanderlisted", "budget"])
async def budget_node(state: TravelAgentState, *, llm, executor) -> dict:
    """Sequential budget node — runs budget agent and extracts structured data."""
    enriched = build_context_messages(state)
    result = await executor.ainvoke({"messages": enriched})
    new_msgs = result["messages"][len(enriched) :]
    components = state.get("itinerary_components", {})

    # Extract structured budget from the agent's free-text output
    budget_data = None
    budget_text = " ".join(
        _extract_text_content(m.content)
        for m in new_msgs
        if isinstance(m, AIMessage) and m.content
    )
    # Also extract target budget from user messages for the extraction context
    user_budget_context = ""
    for m in state.get("messages", []):
        if isinstance(m, HumanMessage) and m.content:
            text = _extract_text_content(m.content)
            if re.search(r"budget|spend|\$[\d,]+", text, re.IGNORECASE):
                user_budget_context = f"\n\nUser's original request: {text}"
                break

    if budget_text:
        try:
            structured_llm = llm.with_structured_output(BudgetBreakdown)
            budget_data = await structured_llm.ainvoke(
                [
                    SystemMessage(
                        content="Extract the budget breakdown from the following text. "
                        "Return all monetary amounts in the currency mentioned. "
                        "If a field is not mentioned, leave it as 0. "
                        "IMPORTANT: Set target_budget to the user's stated maximum/target "
                        "budget from their request. If they said 'budget $2000', set "
                        "target_budget to 2000. If no budget was mentioned, leave it as 0."
                    ),
                    HumanMessage(content=budget_text + user_budget_context),
                ]
            )
        except Exception:
            pass  # Fall back to unstructured — budget_data stays None

    return {
        "messages": new_msgs,
        "current_agent": "budget",
        "itinerary_components": {
            **components,
            "budget": result,
            **({"budget_structured": budget_data.model_dump()} if budget_data else {}),
            "completed_agents": components.get("completed_agents", [])
            + ["BudgetAgent"],
        },
    }


@traceable(run_type="chain", name="itinerary_node", tags=["wanderlisted", "itinerary"])
async def itinerary_node(state: TravelAgentState, *, executor) -> dict:
    """Sequential itinerary node — assembles itinerary from prior agent data."""
    enriched = build_context_messages(state)
    result = await executor.ainvoke({"messages": enriched})
    new_msgs = result["messages"][len(enriched) :]
    components = state.get("itinerary_components", {})
    return {
        "messages": new_msgs,
        "current_agent": "itinerary",
        "itinerary_components": {
            **components,
            "itinerary": result,
            "completed_agents": components.get("completed_agents", [])
            + ["ItineraryAgent"],
        },
    }


@traceable(
    run_type="chain", name="render_handbook_node", tags=["wanderlisted", "render"]
)
async def render_handbook_node(state: TravelAgentState, *, llm) -> dict:
    """Extract structured data from all agent outputs via per-section LLM
    extractions, post-process photo URLs and route maps, then render the
    travel handbook to HTML, Markdown, and JSON."""
    from datetime import datetime
    from pydantic import BaseModel, Field as PydanticField
    from src.agent.renderer import _pick_palette, _get_season
    from src.tools.google_maps import (
        places_photo_url,
        directions_embed_url,
        lookup_place_photo,
    )

    components = state.get("itinerary_components", {})

    # ── Collect per-agent text ────────────────────────────────────────
    def _agent_text(key: str) -> str:
        if key not in components:
            return ""
        msgs = components[key].get("messages", [])
        parts = []
        for m in msgs:
            if isinstance(m, (AIMessage, ToolMessage)) and m.content:
                content = _extract_text_content(m.content)
                parts.append(content)
        return " ".join(parts)

    flights_text = _agent_text("flights")
    hotels_text = _agent_text("hotels")
    destination_text = _agent_text("destination")
    restaurants_text = _agent_text("restaurants")
    activities_text = _agent_text("activities")
    transportation_text = _agent_text("transportation")
    budget_text = _agent_text("budget")
    itinerary_text = _agent_text("itinerary")

    all_text = "\n\n".join(
        filter(
            None,
            [
                f"[FLIGHTS]\n{flights_text}" if flights_text else "",
                f"[HOTELS]\n{hotels_text}" if hotels_text else "",
                f"[DESTINATION]\n{destination_text}" if destination_text else "",
                f"[RESTAURANTS]\n{restaurants_text}" if restaurants_text else "",
                f"[ACTIVITIES]\n{activities_text}" if activities_text else "",
                f"[TRANSPORTATION]\n{transportation_text}"
                if transportation_text
                else "",
                f"[BUDGET]\n{budget_text}" if budget_text else "",
                f"[ITINERARY]\n{itinerary_text}" if itinerary_text else "",
            ],
        )
    )

    # Debug: log text sizes for each section
    for _sec_name, _sec_text in [
        ("flights", flights_text),
        ("hotels", hotels_text),
        ("destination", destination_text),
        ("restaurants", restaurants_text),
        ("activities", activities_text),
        ("transportation", transportation_text),
        ("budget", budget_text),
        ("itinerary", itinerary_text),
    ]:
        _log.debug(f"render_handbook: Section '{_sec_name}': {len(_sec_text)} chars")

    if not all_text.strip():
        return {
            "messages": [
                AIMessage(content="No agent data available to generate handbook.")
            ],
            "current_agent": "render_handbook",
        }

    # ── Lightweight section-extraction models ─────────────────────────

    class ExtractedFlights(BaseModel):
        flights: list[FlightOption] = PydanticField(default_factory=list)

    class ExtractedHotels(BaseModel):
        hotels: list[HotelOption] = PydanticField(default_factory=list)

    class ExtractedDays(BaseModel):
        days: list[DayPlan] = PydanticField(default_factory=list)

    class ExtractedSafety(BaseModel):
        safety: SafetyInfo = PydanticField(default_factory=SafetyInfo)

    class ExtractedCulture(BaseModel):
        culture: CultureGuide = PydanticField(default_factory=CultureGuide)

    class ExtractedPacking(BaseModel):
        packing: list[PackingItem] = PydanticField(default_factory=list)

    class ExtractedMeta(BaseModel):
        trip_title: str = ""
        origin_city: str = ""
        start_date: str = ""
        end_date: str = ""
        route_cities: list[str] = PydanticField(default_factory=list)
        route_transport: list[str] = PydanticField(default_factory=list)
        total_budget_usd: float = 0
        exchange_rate: float = 0
        local_currency_code: str = ""

    # ── Per-section extraction (batched to avoid rate limits) ────────

    async def _extract(
        model_cls,
        text: str,
        instruction: str,
        max_retries: int = 2,
        max_chars: int = 100_000,
    ):
        if not text.strip():
            _log.debug(f"_extract({model_cls.__name__}): empty text, returning default")
            return model_cls()
        s_llm = llm.with_structured_output(model_cls, method="function_calling")
        truncated = text[:max_chars]
        msgs = [
            SystemMessage(content=instruction),
            HumanMessage(content=truncated),
        ]
        for attempt in range(max_retries + 1):
            try:
                result = await s_llm.ainvoke(msgs)
                # Retry once if the primary list field came back empty
                if result:
                    for field_name in ("flights", "hotels", "days", "packing"):
                        val = getattr(result, field_name, None)
                        if isinstance(val, list) and len(val) == 0:
                            _log.debug(
                                f"_extract({model_cls.__name__}): empty {field_name}, retrying"
                            )
                            result = await s_llm.ainvoke(
                                [
                                    SystemMessage(
                                        content=instruction
                                        + "\nIMPORTANT: Extract ALL items. Do NOT return an empty list."
                                    ),
                                    HumanMessage(content=truncated),
                                ]
                            )
                            break
                _log.debug(f"_extract({model_cls.__name__}): success")
                return result
            except Exception as exc:
                if "429" in str(exc) and attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    _log.debug(
                        f"_extract({model_cls.__name__}): rate limited, waiting {wait}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(wait)
                else:
                    _log.error(f"_extract({model_cls.__name__}): FAILED {exc!r}")
                    return model_cls()
        return model_cls()

    # Batch 1: smaller/faster extractions
    flights_ex, hotels_ex, safety_ex, meta_ex = await asyncio.gather(
        _extract(
            ExtractedFlights,
            flights_text,
            "Extract every flight option from the text. Include carrier, flight number, airports, times, duration, stops, cabin class, price. Parse outbound and inbound/return segments separately.",
        ),
        _extract(
            ExtractedHotels,
            hotels_text,
            "Extract every hotel from the text. Include name, star rating, neighbourhood, price per night, total price, room type, check-in/check-out, amenities, photo URLs, Google Maps URL, website URL, description. If photo URLs from Google Places are mentioned (https://places.googleapis.com/...), include them in photo_urls.",
        ),
        _extract(
            ExtractedSafety,
            f"{destination_text}\n\n{budget_text}",
            "Extract safety and practical info from the destination research. Include: "
            "advisory level (green/yellow/orange/red), advisory summary, visa requirements, "
            "health requirements (vaccinations, health risks), emergency numbers (police, ambulance, fire, "
            "tourist police — use known defaults for the country if not in text), "
            "languages spoken, currency name/symbol/code, timezones, seasonal risks, safety tips. "
            "If the text doesn't explicitly state emergency numbers, use the standard ones for the country "
            "(e.g. 112 for EU countries).",
        ),
        _extract(
            ExtractedMeta,
            all_text,
            "Extract trip metadata: trip title, origin city, start/end dates, route cities in order, transport between cities, total budget, exchange rate, local currency code.",
        ),
    )

    # Batch 2: heavier extractions (days is the biggest)
    days_combined_text = f"{itinerary_text}\n\n{restaurants_text}\n\n{activities_text}\n\n{transportation_text}"
    _days_instruction = (
        "Build a COMPLETE day-by-day itinerary covering EVERY day in the trip. "
        "For each day, set day_number, date, city. "
        "Assign activities and restaurants to morning/afternoon/evening time blocks. "
        "Each place needs: name, category, rating, review_count, price_level, address, description, "
        "google_maps_url, website_url, photo_urls (use any Google Places photo URLs mentioned), "
        "latitude, longitude, estimated_cost_usd, estimated_duration_minutes. "
        "Include transit steps between places. Set daily_cost_usd. "
        "Include any cultural tips mentioned for relevant days. "
        "IMPORTANT: You MUST extract ALL days. Do NOT stop early or truncate."
    )
    days_ex, culture_ex, packing_ex = await asyncio.gather(
        _extract(
            ExtractedDays,
            days_combined_text,
            _days_instruction,
        ),
        _extract(
            ExtractedCulture,
            destination_text,
            "Extract cultural info. "
            "For phrases: find all 'Phrase: English → local (romanized)' lines and extract into a list of dicts with keys 'english', 'local', 'romanized'. "
            "Also extract: etiquette tips, tipping guide, dining customs, dress code notes, food specialties, local customs.",
        ),
        _extract(
            ExtractedPacking,
            f"{destination_text}\n\n{itinerary_text}\n\n{activities_text}",
            "Generate a packing list based on the weather, activities, and destination. Each item needs: item name, reason, category (clothing/documents/tech/health/money/activities), essential (bool), weather context, activity context.",
        ),
    )

    # ── Days completion check ─────────────────────────────────────────
    # Detect expected trip length from the itinerary text
    _day_nums_in_text = re.findall(r"[Dd]ay\s+(\d+)", itinerary_text)
    expected_day_count = max((int(n) for n in _day_nums_in_text), default=0)
    extracted_day_count = len(days_ex.days)
    if expected_day_count > 0 and extracted_day_count < expected_day_count:
        _log.warning(
            "Days extraction incomplete: got %d/%d, retrying for missing days",
            extracted_day_count,
            expected_day_count,
        )
        extracted_nums = {d.day_number for d in days_ex.days}
        missing = [
            n for n in range(1, expected_day_count + 1) if n not in extracted_nums
        ]
        if missing:
            days_retry = await _extract(
                ExtractedDays,
                days_combined_text,
                (
                    f"Extract ONLY the following days from the itinerary: days {missing}. "
                    f"The trip has {expected_day_count} total days. "
                    "For each day, set day_number, date, city. "
                    "Assign activities and restaurants to morning/afternoon/evening time blocks. "
                    "Each place needs: name, category, rating, review_count, price_level, "
                    "address, description, google_maps_url, website_url, photo_urls, "
                    "latitude, longitude, estimated_cost_usd, estimated_duration_minutes. "
                    "Include transit steps between places. Set daily_cost_usd."
                ),
            )
            days_ex.days.extend(days_retry.days)
            days_ex.days.sort(key=lambda d: d.day_number)
            _log.info(
                "After retry: %d days extracted (expected %d)",
                len(days_ex.days),
                expected_day_count,
            )

    # ── Filter placeholder results ────────────────────────────────────
    # Remove flights with no actual segment data
    flights_ex.flights = [f for f in flights_ex.flights if f.outbound or f.inbound]
    # Remove hotels with placeholder/hallucinated names
    _PLACEHOLDER_PATTERNS = ("no specific", "not mentioned", "no hotel", "n/a", "none")
    hotels_ex.hotels = [
        h
        for h in hotels_ex.hotels
        if h.name and not any(p in h.name.lower() for p in _PLACEHOLDER_PATTERNS)
    ]

    # ── Assemble TripHandbook ─────────────────────────────────────────
    destinations = state.get("destinations", [])
    season = _get_season(meta_ex.start_date or state.get("start_date", ""))
    palette = _pick_palette(destinations, season)

    handbook = TripHandbook(
        # Meta
        trip_title=meta_ex.trip_title
        or (
            "Trip to " + ", ".join(d.title() for d in destinations)
            if destinations
            else "Your Travel Handbook"
        ),
        origin_city=meta_ex.origin_city,
        destinations=destinations,
        start_date=meta_ex.start_date,
        end_date=meta_ex.end_date,
        total_budget_usd=meta_ex.total_budget_usd,
        travel_style=state.get("travel_style", ""),
        group_type=state.get("group_type", ""),
        dietary_restrictions=state.get("dietary_restrictions", []),
        accessibility_needs=state.get("accessibility_needs", []),
        route_cities=meta_ex.route_cities or [d.title() for d in destinations],
        route_transport=meta_ex.route_transport,
        exchange_rate=meta_ex.exchange_rate,
        local_currency_code=meta_ex.local_currency_code,
        # Core content
        flights=flights_ex.flights,
        hotels=hotels_ex.hotels,
        days=days_ex.days,
        # Info sections
        safety=safety_ex.safety,
        culture=culture_ex.culture,
        packing=packing_ex.packing,
        # Theme
        theme_accent_color=palette.accent,
        hero_gradient_from=palette.gradient_from,
        hero_gradient_to=palette.gradient_to,
        hero_emoji=palette.hero_emoji,
        season=season,
        generated_at=datetime.now().strftime("%B %d, %Y at %H:%M"),
    )

    # Budget overlay from structured extraction
    budget_data = components.get("budget_structured")
    if budget_data and isinstance(budget_data, dict):
        handbook.budget_flights = budget_data.get("flights", 0)
        handbook.budget_accommodation = budget_data.get("accommodation", 0)
        handbook.budget_transport = budget_data.get("transport", 0)
        handbook.budget_meals = budget_data.get("meals", 0)
        handbook.budget_activities = budget_data.get("activities", 0)
        handbook.budget_misc = budget_data.get("misc", 0)
        handbook.budget_total = budget_data.get("total", 0)
        handbook.budget_per_person = budget_data.get("per_person", 0)
        handbook.budget_summary = budget_data.get("summary", "")

    # ── Post-process: photo URLs ──────────────────────────────────────
    # Convert any raw Places photo refs to displayable URLs
    def _fix_photo_urls(urls: list[str]) -> list[str]:
        fixed = []
        for u in urls:
            if u.startswith("places/") and "/photos/" in u:
                try:
                    fixed.append(places_photo_url(u))
                except RuntimeError:
                    pass
            elif u.startswith("http"):
                fixed.append(u)
        return fixed

    # Build a lookup of place-name → photo URL from the raw agent text.
    _photo_pattern = re.compile(
        r"•\s*(.+?)\n(?:.*?\n)*?\s*Photo:\s*(https://places\.googleapis\.com/\S+)",
        re.MULTILINE,
    )
    _standalone_photo = re.compile(
        r"Photo:\s*(https://places\.googleapis\.com/\S+)",
    )
    _name_to_photo: dict[str, str] = {}
    _all_photo_urls: list[str] = []
    for m_text in [restaurants_text, activities_text, hotels_text, destination_text]:
        for m in _photo_pattern.finditer(m_text):
            _name_to_photo[m.group(1).strip().lower()] = m.group(2).strip()
        for m in _standalone_photo.finditer(m_text):
            _all_photo_urls.append(m.group(1).strip())

    def _inject_photos(card, card_name: str = "") -> None:
        """If the card has no photos, try to match from the raw text."""
        card.photo_urls = _fix_photo_urls(card.photo_urls)
        if not card.photo_urls:
            name_key = (card_name or getattr(card, "name", "")).strip().lower()
            if name_key in _name_to_photo:
                card.photo_urls = [_name_to_photo[name_key]]

    # First pass: fix existing photos + regex match
    for hotel in handbook.hotels:
        _inject_photos(hotel)
        if hotel.name and not hotel.map_embed_url:
            from urllib.parse import quote_plus

            maps_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
            if maps_key:
                q = quote_plus(
                    f"{hotel.name}, {hotel.neighbourhood}"
                    if hotel.neighbourhood
                    else hotel.name
                )
                hotel.map_embed_url = f"https://www.google.com/maps/embed/v1/place?key={maps_key}&q={q}&zoom=15"

    for day in handbook.days:
        for block in day.time_blocks:
            for act in block.activities:
                _inject_photos(act)
            if block.restaurant:
                _inject_photos(block.restaurant)

    # Second pass: batch photo lookups via Places API for cards still missing photos
    destinations_str = " ".join(d.title() for d in destinations)

    async def _lookup(name: str) -> tuple[str, str | None]:
        return name, await asyncio.to_thread(lookup_place_photo, name, destinations_str)

    cards_needing_photos: list[Any] = []
    for hotel in handbook.hotels:
        if not hotel.photo_urls and hotel.name:
            cards_needing_photos.append(hotel)
    for day in handbook.days:
        for block in day.time_blocks:
            for act in block.activities:
                if not act.photo_urls and act.name:
                    cards_needing_photos.append(act)
            if (
                block.restaurant
                and not block.restaurant.photo_urls
                and block.restaurant.name
            ):
                cards_needing_photos.append(block.restaurant)

    if cards_needing_photos:
        # Limit to 20 lookups to stay within API quotas and time
        batch = cards_needing_photos[:20]
        results = await asyncio.gather(
            *[_lookup(c.name) for c in batch],
            return_exceptions=True,
        )
        name_to_url: dict[str, str] = {}
        for r in results:
            if isinstance(r, tuple) and r[1]:
                name_to_url[r[0]] = r[1]
        for card in batch:
            url = name_to_url.get(card.name)
            if url:
                card.photo_urls = [url]

    for day in handbook.days:
        # Collect all place names/coords for the day's route map
        day_places: list[str] = []
        for block in day.time_blocks:
            for act in block.activities:
                if act.latitude and act.longitude:
                    day_places.append(f"{act.latitude},{act.longitude}")
                elif act.name:
                    day_places.append(act.name)
            if block.restaurant:
                if block.restaurant.latitude and block.restaurant.longitude:
                    day_places.append(
                        f"{block.restaurant.latitude},{block.restaurant.longitude}"
                    )
                elif block.restaurant.name:
                    day_places.append(block.restaurant.name)

        # Build a route map for the day if there are 2+ stops
        if len(day_places) >= 2 and not day.route_map_url:
            try:
                day.route_map_url = directions_embed_url(
                    origin=day_places[0],
                    destination=day_places[-1],
                    waypoints=day_places[1:-1] if len(day_places) > 2 else None,
                    mode="walking",
                )
            except Exception:
                pass

    # ── Render outputs (offload sync I/O to thread) ─────────────────
    renderer = HandbookRenderer()
    paths = await asyncio.to_thread(renderer.write_outputs, handbook)
    path_strings = {k: str(v) for k, v in paths.items()}

    # Fire-and-forget: log metadata to LangSmith without blocking the response
    sections_generated = [
        k
        for k in [
            "flights",
            "hotels",
            "restaurants",
            "activities",
            "transportation",
            "destination",
            "budget",
            "itinerary",
        ]
        if k in components
    ]
    asyncio.create_task(
        _bg_log_to_langsmith(
            paths=path_strings,
            destinations=state.get("destinations", []),
            sections=sections_generated,
        )
    )

    return {
        "messages": [
            AIMessage(
                content=(
                    f"📘 **Travel Handbook Generated!**\n\n"
                    f"Your complete travel handbook has been saved:\n"
                    f"- 📄 HTML: `{path_strings.get('html', '')}`\n"
                    f"- 📝 Markdown: `{path_strings.get('markdown', '')}`\n"
                    f"- 📊 JSON: `{path_strings.get('json', '')}`\n\n"
                    f"Open the HTML file in your browser for the full "
                    f"interactive experience."
                )
            )
        ],
        "current_agent": "render_handbook",
        "handbook_paths": path_strings,
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
    """Route after triage: shallow queries -> shallow_reply, deep -> supervisor.

    When target_agent is set, always route to supervisor (which will
    short-circuit to only that one agent).
    """
    if state.get("target_agent"):
        return "supervisor"
    agent = state.get("current_agent", "")
    if agent == "triage:shallow":
        return "shallow_reply"
    return "supervisor"


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

    # Fan-out: one Send per requested parallel agent.  LangGraph runs them
    # concurrently and fans-in automatically before safety_review fires.
    parallel_requested = [a for a in routing if a in PARALLEL_AGENTS]
    if parallel_requested:
        return [Send(AGENT_TO_NODE[a], state) for a in parallel_requested]

    # Only sequential agents requested (BudgetAgent or ItineraryAgent)
    if "BudgetAgent" in routing:
        return "budget"
    if "ItineraryAgent" in routing:
        return "itinerary"

    return END


def route_after_safety_review(state: TravelAgentState) -> str:
    """Route after safety review: cancelled -> END, otherwise -> budget or itinerary."""
    if state.get("hitl_action") == "rejected":
        return END

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
    """Route after budget review: rejected -> END, otherwise -> itinerary."""
    if state.get("hitl_action") == "rejected":
        return END

    components = state.get("itinerary_components", {})
    routing = components.get("routing", [])

    if "ItineraryAgent" in routing:
        return "itinerary"
    return END


def route_after_human_review(state: TravelAgentState) -> str:
    """Route after human review: rejected -> END, otherwise -> render_handbook."""
    if state.get("hitl_action") == "rejected":
        return END
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
        "BudgetAgent": llm_fast,  # arithmetic + format
        "DestinationAgent": llm,  # 7 tools — deep synthesis via RAG + web search
        "ItineraryAgent": llm,  # 2 tools — day-plan synthesis across destinations
    }

    agent_classes = {
        "FlightsAgent": FlightsAgent,
        "HotelsAgent": HotelsAgent,
        "DestinationAgent": DestinationAgent,
        "BudgetAgent": BudgetAgent,
        "RestaurantsAgent": RestaurantsAgent,
        "ActivitiesAgent": ActivitiesAgent,
        "TransportationAgent": TransportationAgent,
        "ItineraryAgent": ItineraryAgent,
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

    # --- graph wiring ---------------------------------------------------------

    builder = StateGraph(TravelAgentState)

    # Nodes — thin wrappers that inject dependencies into module-level functions
    #
    # Utility tier (gpt-5.4-nano): triage, shallow_reply, supervisor, render_handbook, synthesize
    # Fast tier (gpt-5.4-mini): Send() worker agents (flights/hotels/restaurants/activities/transport)
    # Reasoning tier (gpt-5.4): destination worker + itinerary sequential node
    builder.add_node("triage", functools.partial(triage_node, llm=llm_utility))
    builder.add_node(
        "shallow_reply", functools.partial(shallow_reply_node, llm=llm_utility)
    )
    builder.add_node(
        "supervisor",
        functools.partial(supervisor_node, supervisor_agent=_supervisor_agent),
    )
    # Send() fan-out worker nodes — each is an independent graph node
    builder.add_node(
        "flights", functools.partial(flights_node, executor=_executors["FlightsAgent"])
    )
    builder.add_node(
        "hotels", functools.partial(hotels_node, executor=_executors["HotelsAgent"])
    )
    builder.add_node(
        "destination",
        functools.partial(destination_node, executor=_executors["DestinationAgent"]),
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
        "budget",
        functools.partial(
            budget_node, llm=llm_utility, executor=_executors["BudgetAgent"]
        ),
    )
    builder.add_node("budget_review", budget_review_node)
    builder.add_node(
        "itinerary",
        functools.partial(itinerary_node, executor=_executors["ItineraryAgent"]),
    )
    builder.add_node("human_review", human_review_node)
    builder.add_node(
        "render_handbook", functools.partial(render_handbook_node, llm=llm_utility)
    )
    builder.add_node("synthesize", functools.partial(synthesize_node, llm=llm_utility))

    # START -> triage
    builder.add_edge(START, "triage")

    # triage -> shallow_reply | supervisor
    builder.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "shallow_reply": "shallow_reply",
            "supervisor": "supervisor",
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
            "hotels",
            "destination",
            "restaurants",
            "activities",
            "transportation",
            "budget",
            "itinerary",
            "synthesize",
            END,
        ],
    )

    # Fan-in: every parallel worker → safety_review.
    # LangGraph waits for ALL Send() instances to complete before firing safety_review.
    for _worker in [
        "flights",
        "hotels",
        "destination",
        "restaurants",
        "activities",
        "transportation",
    ]:
        builder.add_edge(_worker, "safety_review")

    # safety_review -> budget | itinerary | END
    builder.add_conditional_edges(
        "safety_review",
        route_after_safety_review,
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
        {
            "itinerary": "itinerary",
            END: END,
        },
    )

    # itinerary -> human_review -> render_handbook -> END
    builder.add_edge("itinerary", "human_review")

    # human_review -> render_handbook | END
    builder.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
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
