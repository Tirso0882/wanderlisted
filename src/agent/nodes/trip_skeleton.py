"""Select exact trip dates and allocate contiguous city stays."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, ToolMessage
from langsmith import traceable

from custom_logging import AppLogger
from src.agent.state import TravelAgentState
from src.models import (
    ComponentResult,
    ComponentStatus,
    ErrorCategory,
    FlightWindowOption,
    FlightWindowSearchResult,
    TripRequest,
    build_trip_skeleton,
)
from src.tools.iata import resolve_iata_code

_log = AppLogger("agent.nodes.trip_skeleton")
_MARKER = "FLIGHT_WINDOW_RESULT_JSON:\n"


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("text")
        )
    return str(content or "")


def _flight_window_results(state: TravelAgentState) -> list[FlightWindowSearchResult]:
    results: list[FlightWindowSearchResult] = []
    messages = (
        state.get("itinerary_components", {}).get("flights", {}).get("messages", [])
    )
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        if message.name != "search_cheapest_round_trip_in_window":
            continue
        text = _content_text(message.content)
        if _MARKER not in text:
            continue
        try:
            payload = json.loads(text.split(_MARKER, 1)[1])
            results.append(FlightWindowSearchResult.model_validate(payload))
        except (json.JSONDecodeError, ValueError) as exc:
            _log.warning("Invalid flight-window evidence: %s", exc)
    return results


def _selected_flight(
    state: TravelAgentState,
    request: TripRequest,
) -> FlightWindowOption | None:
    duration = request.date_window.duration_days
    candidates = [
        option
        for result in _flight_window_results(state)
        if result.duration_days == duration
        for option in result.options
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda option: float(option.total_amount or "inf"))


@traceable(
    run_type="chain",
    name="trip_skeleton_node",
    tags=["wanderlisted", "trip-skeleton"],
)
async def trip_skeleton_node(state: TravelAgentState) -> dict:
    """Create exact dates and stays from the canonical request and flight evidence."""
    request = TripRequest.model_validate(state.get("trip_request", {}))
    window = request.date_window
    try:
        duration_days = window.duration_days
        if window.exact_start and window.exact_end:
            actual_duration = (window.exact_end - window.exact_start).days + 1
            if duration_days is not None and duration_days != actual_duration:
                raise ValueError(
                    f"exact dates contain {actual_duration} days, not {duration_days}"
                )
            duration_days = actual_duration
            start_date = window.exact_start
            selected_flight = None
        elif window.exact_start and duration_days:
            start_date = window.exact_start
            selected_flight = None
        elif window.flexible and duration_days:
            selected_flight = _selected_flight(state, request)
            if selected_flight is None:
                raise ValueError(
                    "flexible trip dates require a completed typed round-trip flight search"
                )
            start_date = selected_flight.departure_date
        else:
            raise ValueError(
                "exact dates or a usable flexible date window are required"
            )

        if duration_days is None:
            raise ValueError("trip duration is required")
        cities = list(request.destinations)
        return_to_entry = False
        if selected_flight is not None:
            gateway_index = next(
                (
                    index
                    for index, city in enumerate(cities)
                    if resolve_iata_code(city) == selected_flight.destination
                ),
                None,
            )
            if gateway_index is None:
                raise ValueError(
                    "selected flight destination does not match a requested city"
                )
            gateway = cities.pop(gateway_index)
            cities.insert(0, gateway)
            return_to_entry = len(cities) > 1

        skeleton = build_trip_skeleton(
            cities=cities,
            start_date=start_date,
            duration_days=duration_days,
            selected_flight=selected_flight,
            return_to_entry=return_to_entry,
        )
    except (TypeError, ValueError) as exc:
        message = f"Trip skeleton could not be created: {exc}"
        outcome = ComponentResult(
            component="trip_skeleton",
            status=ComponentStatus.FAILED,
            message=message,
            error_category=ErrorCategory.VALIDATION,
            error_detail=str(exc)[:500],
        )
        return {
            "messages": [AIMessage(content=message)],
            "current_agent": "trip_skeleton:failed",
            "workflow_status": "failed",
            "component_results": {"trip_skeleton": outcome.model_dump(mode="json")},
        }

    skeleton_json = skeleton.model_dump_json(indent=2)
    message = AIMessage(content=f"TRIP_SKELETON_JSON:\n{skeleton_json}")
    outcome = ComponentResult(
        component="trip_skeleton",
        status=ComponentStatus.COMPLETED,
        data=skeleton.model_dump(mode="json"),
        message="Exact trip dates and city stays selected.",
        evidence_count=1 if skeleton.selected_flight else 0,
    )
    components = state.get("itinerary_components", {})
    return {
        "messages": [message],
        "current_agent": "trip_skeleton:completed",
        "workflow_status": "skeleton_ready",
        "start_date": skeleton.start_date.isoformat(),
        "end_date": skeleton.end_date.isoformat(),
        "itinerary_components": {
            **components,
            "trip_skeleton": {"messages": [message]},
            "trip_skeleton_structured": skeleton.model_dump(mode="json"),
        },
        "component_results": {"trip_skeleton": outcome.model_dump(mode="json")},
    }
