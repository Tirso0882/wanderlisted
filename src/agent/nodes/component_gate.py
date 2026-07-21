"""Fan-in completeness gate for requested discovery components."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langsmith import traceable

from src.agent.state import TravelAgentState
from src.models import ComponentStatus, TripRequest

_AGENT_COMPONENT = {
    "FlightsAgent": "flights",
    "HotelsAgent": "hotels",
    "DestinationAgent": "destination",
    "RestaurantsAgent": "restaurants",
    "ActivitiesAgent": "activities",
}

_STATUS_PRIORITY = (
    ComponentStatus.NEEDS_USER_INPUT,
    ComponentStatus.BLOCKED_EXTERNAL,
    ComponentStatus.NO_INVENTORY,
    ComponentStatus.FAILED,
)


def _blocked_message(blocked: list[tuple[str, str, str]], locale: str) -> str:
    if locale == "pl":
        heading = "Nie mogę jeszcze bezpiecznie ukończyć pełnego planu:"
        next_step = "Uzupełnij brakujące dane lub poproś o ponowienie wyszukiwania."
    else:
        heading = "I cannot safely complete the full plan yet:"
        next_step = "Provide the missing details or ask me to retry the search."
    lines = [heading]
    for component, status, message in blocked:
        detail = message.strip().splitlines()[0][:240] if message.strip() else status
        lines.append(f"- {component}: {detail}")
    lines.append(next_step)
    return "\n".join(lines)


@traceable(
    run_type="chain",
    name="component_gate_node",
    tags=["wanderlisted", "completion-gate"],
)
async def component_gate_node(
    state: TravelAgentState,
    *,
    eligible_components: set[str] | None = None,
) -> dict:
    """Block dependent planning unless every requested discovery task completed."""
    routing = state.get("itinerary_components", {}).get("routing", [])
    outcomes = state.get("component_results", {})
    selected = [
        _AGENT_COMPONENT[agent]
        for agent in routing
        if agent in _AGENT_COMPONENT
        and (
            eligible_components is None
            or _AGENT_COMPONENT[agent] in eligible_components
        )
    ]

    blocked: list[tuple[str, str, str]] = []
    for component in selected:
        result = outcomes.get(component)
        if not result:
            blocked.append(
                (component, ComponentStatus.FAILED, "Missing component outcome")
            )
            continue
        status = result.get("status", ComponentStatus.FAILED)
        if status != ComponentStatus.COMPLETED:
            blocked.append((component, status, result.get("message", "")))

    if not blocked:
        return {
            "current_agent": "component_gate:ready",
            "workflow_status": "planning",
        }

    status = next(
        (
            candidate
            for candidate in _STATUS_PRIORITY
            if any(item[1] == candidate for item in blocked)
        ),
        ComponentStatus.FAILED,
    )
    request = TripRequest.model_validate(state.get("trip_request", {}))
    pending = [
        component
        for component, component_status, _ in blocked
        if component_status == ComponentStatus.NEEDS_USER_INPUT
    ]
    return {
        "messages": [AIMessage(content=_blocked_message(blocked, request.locale))],
        "current_agent": f"component_gate:{status}",
        "workflow_status": status,
        "pending_questions": pending,
    }
