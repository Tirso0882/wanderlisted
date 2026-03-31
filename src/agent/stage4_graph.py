"""Stage 4: Multi-Agent Supervisor Graph using LangGraph.

Parallel multi-agent architecture: the supervisor decides which specialist
agents are needed, then independent agents (Flights, Hotels, Destination,
Restaurants, Activities, Transportation) run in parallel.  Dependent agents
(Budget, Itinerary) run sequentially afterward since they need the earlier
results.

Flow (parallel phase → sequential phase):
    START → supervisor → parallel_fan_out ──┬── flights ─────┐
                                            ├── hotels ──────┤
                                            ├── destination ─┤
                                            ├── restaurants ──┤ → join → budget → itinerary → END
                                            ├── activities ──┤
                                            └── transportation┘

Usage:
    from src.agent.stage4_graph import graph
    result = graph.invoke(
        {"messages": [HumanMessage("Plan my Tokyo trip")]},
        {"configurable": {"thread_id": "abc"}},
    )
"""

import asyncio
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

from src.agent.llm import get_llm
from src.agent.state import TravelAgentState
from src.agent.prompts import (
    SYNTHESIZE_SYSTEM_PROMPT,
    TRIAGE_SYSTEM_PROMPT,
    HANDBOOK_ASSEMBLY_PROMPT,
)
from src.models import BudgetBreakdown
from src.models.itinerary import TripHandbook
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

PARALLEL_AGENTS = _routing_cfg.get("parallel_agents", [
    "FlightsAgent", "HotelsAgent", "DestinationAgent",
    "RestaurantsAgent", "ActivitiesAgent", "TransportationAgent",
])
SEQUENTIAL_AGENTS = _routing_cfg.get("sequential_agents", [
    "BudgetAgent", "ItineraryAgent",
])

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


def create_multiagent_travel_graph(checkpointer=None):
    """Create a LangGraph with supervisor, parallel specialist dispatch, and sequential finishers."""

    llm = get_llm()

    # --- agents & executors ---------------------------------------------------
    supervisor_agent = SupervisorAgent(llm)

    flights_agent = FlightsAgent(llm)
    flights_executor = create_agent(
        model=llm,
        tools=flights_agent.tools,
        system_prompt=flights_agent.system_prompt,
    )

    hotels_agent = HotelsAgent(llm)
    hotels_executor = create_agent(
        model=llm,
        tools=hotels_agent.tools,
        system_prompt=hotels_agent.system_prompt,
    )

    destination_agent = DestinationAgent(llm)
    destination_executor = create_agent(
        model=llm,
        tools=destination_agent.tools,
        system_prompt=destination_agent.system_prompt,
    )

    budget_agent = BudgetAgent(llm)
    budget_executor = create_agent(
        model=llm,
        tools=budget_agent.tools,
        system_prompt=budget_agent.system_prompt,
    )

    restaurants_agent = RestaurantsAgent(llm)
    restaurants_executor = create_agent(
        model=llm,
        tools=restaurants_agent.tools,
        system_prompt=restaurants_agent.system_prompt,
    )

    activities_agent = ActivitiesAgent(llm)
    activities_executor = create_agent(
        model=llm,
        tools=activities_agent.tools,
        system_prompt=activities_agent.system_prompt,
    )

    transportation_agent = TransportationAgent(llm)
    transportation_executor = create_agent(
        model=llm,
        tools=transportation_agent.tools,
        system_prompt=transportation_agent.system_prompt,
    )

    itinerary_agent = ItineraryAgent(llm)
    itinerary_executor = create_agent(
        model=llm,
        tools=itinerary_agent.tools,
        system_prompt=itinerary_agent.system_prompt,
    )

    executors = {
        "FlightsAgent": flights_executor,
        "HotelsAgent": hotels_executor,
        "DestinationAgent": destination_executor,
        "BudgetAgent": budget_executor,
        "RestaurantsAgent": restaurants_executor,
        "ActivitiesAgent": activities_executor,
        "TransportationAgent": transportation_executor,
        "ItineraryAgent": itinerary_executor,
    }

    # --- helpers --------------------------------------------------------------

    def _build_user_profile_context(state: TravelAgentState) -> str:
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
            parts.append(f"Dietary restrictions: {', '.join(state['dietary_restrictions'])}")
        if not parts:
            return ""
        return "USER PROFILE:\n" + "\n".join(parts)

    def _build_context_messages(state: TravelAgentState) -> list:
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
                    m.content for m in agent_msgs
                    if isinstance(m, AIMessage) and m.content
                )
                if summary:
                    parts.append(f"[{label}]\n{summary}")

        msgs = list(state["messages"])

        # Inject user profile
        profile = _build_user_profile_context(state)
        if profile:
            msgs.insert(0, SystemMessage(content=profile))

        if parts:
            context = (
                "Here is what specialist agents found. "
                "Use this context to give a more informed answer.\n\n"
                + "\n\n".join(parts)
            )
            msgs.insert(0, SystemMessage(content=context))
        return msgs

    # --- generic agent runner -------------------------------------------------

    async def _run_agent(agent_name: str, state: TravelAgentState) -> dict:
        """Run a single specialist agent and return its results dict."""
        executor = executors[agent_name]
        enriched = _build_context_messages(state)
        result = await executor.ainvoke({"messages": enriched})
        new_msgs = result["messages"][len(enriched):]
        return {"messages": new_msgs, "data_key": AGENT_TO_NODE[agent_name], "result": result}

    # --- node functions -------------------------------------------------------

    async def triage_node(state: TravelAgentState) -> dict:
        """Lightweight classifier: decide if the query needs the full pipeline (deep)
        or can be answered directly (shallow)."""
        last_message = state["messages"][-1]
        response = await llm.ainvoke([
            SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
            HumanMessage(content=last_message.content),
        ])
        classification = response.content.strip().lower()
        # Default to deep if the LLM returns anything unexpected
        route = "shallow" if classification == "shallow" else "deep"
        return {"current_agent": f"triage:{route}"}

    async def shallow_reply_node(state: TravelAgentState) -> dict:
        """Answer simple queries (greetings, confirmations, clarifications)
        without invoking the supervisor or any specialist agents."""
        enriched = _build_context_messages(state)
        response = await llm.ainvoke([
            SystemMessage(
                content=(
                    "You are a friendly travel planning assistant called Wanderlisted. "
                    "Answer the user's casual message briefly. If they seem to want "
                    "travel planning help, invite them to ask about destinations, "
                    "flights, hotels, activities, or budgets."
                ),
            ),
            *enriched,
        ])
        return {"messages": [response], "current_agent": "shallow_reply"}

    async def supervisor_node(state: TravelAgentState) -> dict:
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
            last_message.content, existing_summary,
        )

        # Merge user profile: keep existing values, override only if new non-empty
        new_destinations = decision.destinations or state.get("destinations", [])
        new_travel_style = decision.travel_style or state.get("travel_style", "")
        new_group_type = decision.group_type or state.get("group_type", "")
        new_accessibility = decision.accessibility_needs or state.get("accessibility_needs", [])
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

    async def parallel_dispatch_node(state: TravelAgentState) -> dict:
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
        tasks = [_run_agent(agent_name, state) for agent_name in to_run]
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

    async def budget_node(state: TravelAgentState) -> dict:
        enriched = _build_context_messages(state)
        result = await executors["BudgetAgent"].ainvoke({"messages": enriched})
        new_msgs = result["messages"][len(enriched):]
        components = state.get("itinerary_components", {})

        # Extract structured budget from the agent's free-text output
        budget_data = None
        budget_text = " ".join(
            m.content for m in new_msgs if isinstance(m, AIMessage) and m.content
        )
        if budget_text:
            try:
                structured_llm = llm.with_structured_output(BudgetBreakdown)
                budget_data = await structured_llm.ainvoke([
                    SystemMessage(
                        content="Extract the budget breakdown from the following text. "
                        "Return all monetary amounts in the currency mentioned. "
                        "If a field is not mentioned, leave it as 0."
                    ),
                    HumanMessage(content=budget_text),
                ])
            except Exception:
                pass  # Fall back to unstructured — budget_data stays None

        return {
            "messages": new_msgs,
            "current_agent": "budget",
            "itinerary_components": {
                **components,
                "budget": result,
                **({"budget_structured": budget_data.model_dump()} if budget_data else {}),
                "completed_agents": components.get("completed_agents", []) + ["BudgetAgent"],
            },
        }

    async def itinerary_node(state: TravelAgentState) -> dict:
        enriched = _build_context_messages(state)
        result = await executors["ItineraryAgent"].ainvoke({"messages": enriched})
        new_msgs = result["messages"][len(enriched):]
        components = state.get("itinerary_components", {})
        return {
            "messages": new_msgs,
            "current_agent": "itinerary",
            "itinerary_components": {
                **components,
                "itinerary": result,
                "completed_agents": components.get("completed_agents", []) + ["ItineraryAgent"],
            },
        }

    async def render_handbook_node(state: TravelAgentState) -> dict:
        """Extract structured data from all agent outputs and render the
        travel handbook to HTML, Markdown, and JSON."""
        components = state.get("itinerary_components", {})

        # Collect all AI-produced text from every agent for structured extraction
        all_agent_text_parts = []
        label_map = {
            "flights": "FLIGHTS DATA",
            "hotels": "HOTELS DATA",
            "destination": "DESTINATION DATA",
            "budget": "BUDGET DATA",
            "restaurants": "RESTAURANTS DATA",
            "activities": "ACTIVITIES DATA",
            "transportation": "TRANSPORTATION DATA",
            "itinerary": "ITINERARY (day-by-day plan)",
        }
        for key, label in label_map.items():
            if key in components:
                agent_msgs = components[key].get("messages", [])
                text = " ".join(
                    m.content for m in agent_msgs
                    if isinstance(m, AIMessage) and m.content
                )
                if text:
                    all_agent_text_parts.append(f"[{label}]\n{text}")

        if not all_agent_text_parts:
            return {
                "messages": [AIMessage(content="No agent data available to generate handbook.")],
                "current_agent": "render_handbook",
            }

        combined_text = "\n\n".join(all_agent_text_parts)

        # Use LLM to extract structured TripHandbook from agent outputs
        renderer = HandbookRenderer()
        try:
            structured_llm = llm.with_structured_output(TripHandbook)
            handbook = await structured_llm.ainvoke([
                SystemMessage(content=HANDBOOK_ASSEMBLY_PROMPT),
                HumanMessage(content=combined_text),
            ])
        except Exception:
            # Fallback: build handbook from state metadata only
            handbook = renderer.build_handbook(state)

        # Overlay state metadata the LLM might have missed
        handbook.destinations = handbook.destinations or state.get("destinations", [])
        handbook.travel_style = handbook.travel_style or state.get("travel_style", "")
        handbook.group_type = handbook.group_type or state.get("group_type", "")
        handbook.dietary_restrictions = (
            handbook.dietary_restrictions or state.get("dietary_restrictions", [])
        )
        handbook.accessibility_needs = (
            handbook.accessibility_needs or state.get("accessibility_needs", [])
        )

        # Overlay budget from the structured extraction if available
        budget_data = components.get("budget_structured")
        if budget_data and isinstance(budget_data, dict) and not handbook.budget_total:
            handbook.budget_flights = budget_data.get("flights", 0)
            handbook.budget_accommodation = budget_data.get("accommodation", 0)
            handbook.budget_transport = budget_data.get("transport", 0)
            handbook.budget_meals = budget_data.get("meals", 0)
            handbook.budget_activities = budget_data.get("activities", 0)
            handbook.budget_misc = budget_data.get("misc", 0)
            handbook.budget_total = budget_data.get("total", 0)
            handbook.budget_per_person = budget_data.get("per_person", 0)

        # Fill generated timestamp and theme
        from datetime import datetime
        handbook.generated_at = handbook.generated_at or datetime.now().strftime(
            "%B %d, %Y at %H:%M"
        )
        if not handbook.trip_title and handbook.destinations:
            handbook.trip_title = (
                "Trip to " + ", ".join(d.title() for d in handbook.destinations)
            )
        if not handbook.theme_accent_color or handbook.theme_accent_color == "#e41e3f":
            from src.agent.renderer import _pick_accent
            handbook.theme_accent_color = _pick_accent(handbook.destinations)

        # Render outputs
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

    async def synthesize_node(state: TravelAgentState) -> dict:
        """Answer follow-up questions from existing specialist data without re-running tools."""
        enriched = _build_context_messages(state)
        response = await llm.ainvoke([
            SystemMessage(content=SYNTHESIZE_SYSTEM_PROMPT),
            *enriched,
        ])
        return {
            "messages": [response],
            "current_agent": "synthesize",
        }

    # --- routing functions ────────────────────────────────────────────────

    def _after_triage(state: TravelAgentState) -> str:
        """Route after triage: shallow queries → shallow_reply, deep → supervisor."""
        agent = state.get("current_agent", "")
        if agent == "triage:shallow":
            return "shallow_reply"
        return "supervisor"

    def _after_supervisor(state: TravelAgentState) -> str:
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

    def _after_parallel(state: TravelAgentState) -> str:
        """Route after parallel phase: run Budget if requested, then Itinerary, else END."""
        components = state.get("itinerary_components", {})
        routing = components.get("routing", [])

        if "BudgetAgent" in routing:
            return "budget"
        if "ItineraryAgent" in routing:
            return "itinerary"
        return END

    def _after_budget(state: TravelAgentState) -> str:
        """Route after budget: run Itinerary if requested, else END."""
        components = state.get("itinerary_components", {})
        routing = components.get("routing", [])

        if "ItineraryAgent" in routing:
            return "itinerary"
        return END

    # --- graph wiring ---------------------------------------------------------

    builder = StateGraph(TravelAgentState)

    builder.add_node("triage", triage_node)
    builder.add_node("shallow_reply", shallow_reply_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("parallel_dispatch", parallel_dispatch_node)
    builder.add_node("budget", budget_node)
    builder.add_node("itinerary", itinerary_node)
    builder.add_node("render_handbook", render_handbook_node)
    builder.add_node("synthesize", synthesize_node)

    # START → triage
    builder.add_edge(START, "triage")

    # triage → shallow_reply | supervisor
    builder.add_conditional_edges("triage", _after_triage, {
        "shallow_reply": "shallow_reply",
        "supervisor": "supervisor",
    })

    # shallow_reply always ends
    builder.add_edge("shallow_reply", END)

    # supervisor → parallel_dispatch | budget | itinerary | synthesize | END
    builder.add_conditional_edges("supervisor", _after_supervisor, {
        "parallel_dispatch": "parallel_dispatch",
        "budget": "budget",
        "itinerary": "itinerary",
        "synthesize": "synthesize",
        END: END,
    })

    # parallel_dispatch → budget | itinerary | END
    builder.add_conditional_edges("parallel_dispatch", _after_parallel, {
        "budget": "budget",
        "itinerary": "itinerary",
        END: END,
    })

    # budget → itinerary | END
    builder.add_conditional_edges("budget", _after_budget, {
        "itinerary": "itinerary",
        END: END,
    })

    # itinerary → render_handbook → END
    builder.add_edge("itinerary", "render_handbook")
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
