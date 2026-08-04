"""Hermetic graph regression for a focused Budget-only request."""

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from src.agent.agents.supervisor_agent import RoutingDecision
from src.agent.stage4_graph import (
    route_after_budget,
    route_after_budget_review,
    route_after_supervisor,
    supervisor_node,
)
from src.agent.state import TravelAgentState


class _OvereagerSupervisor:
    async def aget_routing_decision(self, *_args, **_kwargs):
        return RoutingDecision(
            agents=["BudgetAgent", "ItineraryAgent"],
            reasoning="The model tried to expand the requested scope.",
            user_message="I will estimate the budget.",
            destinations=["bali"],
        )


async def _supervisor(state: TravelAgentState) -> dict:
    return await supervisor_node(state, supervisor_agent=_OvereagerSupervisor())


async def _budget(_state: TravelAgentState) -> dict:
    return {
        "current_agent": "budget",
        "itinerary_components": {
            "budget_structured": {"total": 1250.0, "currency": "USD"}
        },
    }


async def _budget_review(_state: TravelAgentState) -> dict:
    return {"current_agent": "budget_review", "hitl_action": "proceed"}


async def _unexpected_itinerary(_state: TravelAgentState) -> dict:
    raise AssertionError("focused Budget flow must not execute Itinerary")


def _focused_budget_graph():
    builder = StateGraph(TravelAgentState)
    builder.add_node("supervisor", _supervisor)
    builder.add_node("budget", _budget)
    builder.add_node("budget_review", _budget_review)
    builder.add_node("itinerary", _unexpected_itinerary)
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"budget": "budget", "itinerary": "itinerary", END: END},
    )
    builder.add_conditional_edges(
        "budget", route_after_budget, {"budget_review": "budget_review"}
    )
    builder.add_conditional_edges(
        "budget_review",
        route_after_budget_review,
        {"budget": "budget", "itinerary": "itinerary", END: END},
    )
    return builder.compile()


async def test_focused_budget_flow_ends_without_itinerary_artifacts():
    result = await _focused_budget_graph().ainvoke(
        {
            "messages": [HumanMessage(content="How much would a week in Bali cost?")],
            "trip_request": {
                "scope": "focused",
                "destinations": ["bali"],
                "date_window": {"duration_days": 7},
                "travelers": {"adults": 1},
                "requested_capabilities": ["budget"],
            },
            "itinerary_components": {},
        }
    )

    components = result["itinerary_components"]
    assert components["routing"] == ["BudgetAgent"]
    assert components["budget_structured"]["total"] == 1250.0
    assert "itinerary_structured" not in components
    assert result["current_agent"] == "budget_review"
