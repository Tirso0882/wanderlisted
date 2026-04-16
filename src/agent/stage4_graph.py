"""Stage 4: Multi-Agent Supervisor Graph using LangGraph.

Parallel multi-agent architecture: the supervisor decides which specialist
agents are needed, then independent agents (Flights, Hotels, Destination,
Restaurants, Activities, Transportation) run in parallel.  Dependent agents
(Budget, Itinerary) run sequentially afterward since they need the earlier
results.

Flow (parallel phase → sequential phase → HITL review → render):
    START → triage → supervisor → parallel_dispatch ──┬── flights ────┐
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
from langgraph.types import interrupt
from langsmith import traceable

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
                m.content for m in agent_msgs if isinstance(m, AIMessage) and m.content
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


async def safety_review_node(state: TravelAgentState) -> dict:
    """HITL gate: interrupt when safety advisory is 'do not travel' or 'red'.

    Checks destination agent results for dangerous advisory levels.
    If dangerous, pauses execution so the user can acknowledge the risk
    or cancel the trip.
    """
    components = state.get("itinerary_components", {})
    destination_data = components.get("destination", {})

    # Extract safety text from destination agent output
    safety_text = ""
    for m in destination_data.get("messages", []):
        if isinstance(m, (AIMessage, ToolMessage)) and m.content:
            content = m.content if isinstance(m.content, str) else str(m.content)
            safety_text += content.lower()

    # Check for dangerous advisory levels
    danger_keywords = [
        "do not travel",
        "level 4",
        "advisory level: red",
        "reconsider travel",
        "level 3",
    ]
    is_dangerous = any(kw in safety_text for kw in danger_keywords)

    if is_dangerous and not state.get("safety_acknowledged"):
        # Interrupt — user must acknowledge
        decision = interrupt(
            {
                "type": "safety_warning",
                "message": (
                    "⚠️ SAFETY ADVISORY: The destination has a high-risk travel advisory. "
                    "Review the safety information and decide whether to proceed."
                ),
                "action_required": "Respond with {'approved': true} to proceed or {'approved': false} to cancel.",
            }
        )

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
    """
    components = state.get("itinerary_components", {})
    budget_data = components.get("budget_structured", {})

    if not budget_data:
        return {"current_agent": "budget_review"}

    total_estimated = budget_data.get("total", 0)
    # Try to find the user's target budget from the conversation
    budget_text = ""
    for m in state.get("messages", []):
        if isinstance(m, HumanMessage) and m.content:
            budget_text += m.content.lower()

    # Extract target from budget agent's analysis
    target_budget = budget_data.get("target_budget", 0)
    if not target_budget:
        # No explicit target — skip review
        return {"current_agent": "budget_review"}

    overspend = total_estimated - target_budget
    if overspend > 500 and not state.get("budget_adjustment_accepted"):
        decision = interrupt(
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
                    "Respond with {'approved': true} to proceed as-is, "
                    "or {'approved': true, 'feedback': 'your adjustments'} to adjust."
                ),
            }
        )

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
    """
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
            itinerary_preview += m.content[:2000]
            break

    decision = interrupt(
        {
            "type": "itinerary_review",
            "message": "📋 Your travel plan is ready for review before generating the final handbook.",
            "components_available": summary_parts,
            "itinerary_preview": itinerary_preview[:2000],
            "action_required": (
                "Respond with {'approved': true} to generate the handbook, "
                "{'approved': true, 'feedback': 'changes...'} to proceed with notes, "
                "or {'approved': false} to cancel."
            ),
        }
    )

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
    classification = response.content.strip().lower()
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

    last_message = state["messages"][-1]
    decision = await supervisor_agent.aget_routing_decision(
        last_message.content,
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


@traceable(
    run_type="chain", name="parallel_dispatch_node", tags=["wanderlisted", "parallel"]
)
async def parallel_dispatch_node(state: TravelAgentState, *, executors: dict) -> dict:
    """Run all requested parallel agents concurrently, then return merged results."""
    components = state.get("itinerary_components", {})
    routing = components.get("routing", [])

    # Filter to only the parallel-eligible agents that were requested
    to_run = [a for a in routing if a in PARALLEL_AGENTS]

    if not to_run:
        # Nothing to run in parallel — pass through
        return {
            "current_agent": "parallel_dispatch",
            "itinerary_components": {
                **components,
                "completed_agents": components.get("completed_agents", []),
            },
        }

    # Run all parallel agents concurrently
    tasks = [run_agent(agent_name, state, executors=executors) for agent_name in to_run]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge results into components
    all_new_msgs = []
    merged_components = dict(components)
    completed = list(merged_components.get("completed_agents", []))

    for agent_name, result in zip(to_run, results):
        if isinstance(result, Exception):
            all_new_msgs.append(
                AIMessage(content=f"[{agent_name}] encountered an error: {result}")
            )
            continue
        all_new_msgs.extend(result["messages"])
        merged_components[result["data_key"]] = result["result"]
        completed.append(agent_name)

    merged_components["completed_agents"] = completed

    return {
        "messages": all_new_msgs,
        "current_agent": "parallel_dispatch",
        "itinerary_components": merged_components,
    }


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
        m.content for m in new_msgs if isinstance(m, AIMessage) and m.content
    )
    if budget_text:
        try:
            structured_llm = llm.with_structured_output(BudgetBreakdown)
            budget_data = await structured_llm.ainvoke(
                [
                    SystemMessage(
                        content="Extract the budget breakdown from the following text. "
                        "Return all monetary amounts in the currency mentioned. "
                        "If a field is not mentioned, leave it as 0."
                    ),
                    HumanMessage(content=budget_text),
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
                content = m.content if isinstance(m.content, str) else str(m.content)
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
    from custom_logging import AppLogger as _AL

    _render_log = _AL(logger_name="agent.render_handbook", level="DEBUG")
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
        _render_log.debug(f"Section '{_sec_name}': {len(_sec_text)} chars")

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

    async def _extract(model_cls, text: str, instruction: str, max_retries: int = 2):
        if not text.strip():
            _render_log.debug(
                f"_extract({model_cls.__name__}): empty text, returning default"
            )
            return model_cls()
        s_llm = llm.with_structured_output(model_cls, method="function_calling")
        msgs = [
            SystemMessage(content=instruction),
            HumanMessage(content=text[:15000]),
        ]
        for attempt in range(max_retries + 1):
            try:
                result = await s_llm.ainvoke(msgs)
                # Retry once if the primary list field came back empty
                if result:
                    for field_name in ("flights", "hotels", "days", "packing"):
                        val = getattr(result, field_name, None)
                        if isinstance(val, list) and len(val) == 0:
                            _render_log.debug(
                                f"_extract({model_cls.__name__}): empty {field_name}, retrying"
                            )
                            result = await s_llm.ainvoke(
                                [
                                    SystemMessage(
                                        content=instruction
                                        + "\nIMPORTANT: Extract ALL items. Do NOT return an empty list."
                                    ),
                                    HumanMessage(content=text[:15000]),
                                ]
                            )
                            break
                _render_log.debug(f"_extract({model_cls.__name__}): success")
                return result
            except Exception as exc:
                if "429" in str(exc) and attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    _render_log.debug(
                        f"_extract({model_cls.__name__}): rate limited, waiting {wait}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(wait)
                else:
                    _render_log.error(f"_extract({model_cls.__name__}): FAILED {exc!r}")
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
            destination_text,
            "Extract safety info: advisory level (green/yellow/orange/red), summary, visa requirements, health requirements, emergency numbers, languages, currency name/symbol/code, timezones, seasonal risks, safety tips.",
        ),
        _extract(
            ExtractedMeta,
            all_text,
            "Extract trip metadata: trip title, origin city, start/end dates, route cities in order, transport between cities, total budget, exchange rate, local currency code.",
        ),
    )

    # Batch 2: heavier extractions (days is the biggest)
    days_ex, culture_ex, packing_ex = await asyncio.gather(
        _extract(
            ExtractedDays,
            f"{itinerary_text}\n\n{restaurants_text}\n\n{activities_text}\n\n{transportation_text}",
            (
                "Build a day-by-day itinerary. For each day, set day_number, date, city. "
                "Assign activities and restaurants to morning/afternoon/evening time blocks. "
                "Each place needs: name, category, rating, review_count, price_level, address, description, "
                "google_maps_url, website_url, photo_urls (use any Google Places photo URLs mentioned), "
                "latitude, longitude, estimated_cost_usd, estimated_duration_minutes. "
                "Include transit steps between places. Set daily_cost_usd. "
                "Include any cultural tips mentioned for relevant days."
            ),
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

    # ── Render outputs ────────────────────────────────────────────────
    renderer = HandbookRenderer()
    paths = renderer.write_outputs(handbook)
    path_strings = {k: str(v) for k, v in paths.items()}

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
    """Route after triage: shallow queries -> shallow_reply, deep -> supervisor."""
    agent = state.get("current_agent", "")
    if agent == "triage:shallow":
        return "shallow_reply"
    return "supervisor"


def route_after_supervisor(state: TravelAgentState) -> str:
    """Route after supervisor: fan-out to parallel agents, or sequential, or synthesize."""
    components = state.get("itinerary_components", {})
    routing = components.get("routing", [])

    if not routing:
        # No agents requested — check if follow-up synthesis is needed
        has_data = any(k in components for k in DATA_KEYS)
        if has_data:
            return "synthesize"
        return END

    # Check if any parallel agents are requested
    has_parallel = any(a in PARALLEL_AGENTS for a in routing)
    if has_parallel:
        return "parallel_dispatch"

    # Only sequential agents requested (BudgetAgent or ItineraryAgent)
    if "BudgetAgent" in routing:
        return "budget"
    if "ItineraryAgent" in routing:
        return "itinerary"

    return END


def route_after_parallel(state: TravelAgentState) -> str:
    """Route after parallel phase: go to safety review first."""
    return "safety_review"


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
    """Create a LangGraph with supervisor, parallel specialist dispatch, and sequential finishers."""

    llm = get_llm()

    # --- agents & executors ---------------------------------------------------
    _supervisor_agent = SupervisorAgent(llm)

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
        agent = cls(llm)
        _executors[name] = create_agent(
            model=llm,
            tools=agent.tools,
            system_prompt=agent.system_prompt,
        )

    # --- graph wiring ---------------------------------------------------------

    builder = StateGraph(TravelAgentState)

    # Nodes — thin wrappers that inject dependencies into module-level functions
    builder.add_node("triage", functools.partial(triage_node, llm=llm))
    builder.add_node("shallow_reply", functools.partial(shallow_reply_node, llm=llm))
    builder.add_node(
        "supervisor", functools.partial(supervisor_node, supervisor_agent=_supervisor_agent)
    )
    builder.add_node(
        "parallel_dispatch", functools.partial(parallel_dispatch_node, executors=_executors)
    )
    builder.add_node("safety_review", safety_review_node)
    builder.add_node(
        "budget", functools.partial(budget_node, llm=llm, executor=_executors["BudgetAgent"])
    )
    builder.add_node("budget_review", budget_review_node)
    builder.add_node(
        "itinerary", functools.partial(itinerary_node, executor=_executors["ItineraryAgent"])
    )
    builder.add_node("human_review", human_review_node)
    builder.add_node("render_handbook", functools.partial(render_handbook_node, llm=llm))
    builder.add_node("synthesize", functools.partial(synthesize_node, llm=llm))

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

    # supervisor -> parallel_dispatch | budget | itinerary | synthesize | END
    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "parallel_dispatch": "parallel_dispatch",
            "budget": "budget",
            "itinerary": "itinerary",
            "synthesize": "synthesize",
            END: END,
        },
    )

    # parallel_dispatch -> safety_review (always)
    builder.add_conditional_edges(
        "parallel_dispatch",
        route_after_parallel,
        {
            "safety_review": "safety_review",
        },
    )

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
