"""Tests for canonical multi-turn travel request contracts."""

from src.models import (
    ComponentResult,
    ComponentStatus,
    DateWindowPatch,
    ErrorCategory,
    RequestScope,
    RequestedCapability,
    TravelerPartyPatch,
    TripRequestPatch,
    merge_trip_request,
)


def test_trip_request_merges_clarification_without_erasing_first_turn():
    first = merge_trip_request(
        None,
        TripRequestPatch(
            scope=RequestScope.FULL_ITINERARY,
            locale="pl",
            origin_country="Kolumbia",
            destinations=["Krakow", "Warszawa", "Wroclaw", "Gdansk"],
            requested_capabilities=list(RequestedCapability),
            date_window=DateWindowPatch(
                earliest_start="2026-08-20",
                latest_end="2026-09-20",
                duration_days=14,
                flexible=True,
            ),
        ),
    )

    merged = merge_trip_request(
        first,
        TripRequestPatch(
            locale="pl",
            origin_city="Bogota",
            travelers=TravelerPartyPatch(adults=1),
        ),
    )

    assert merged.origin_country == "Kolumbia"
    assert merged.origin_city == "Bogota"
    assert merged.travelers.adults == 1
    assert merged.destinations == ["krakow", "warszawa", "wroclaw", "gdansk"]
    assert merged.date_window.duration_days == 14
    assert merged.date_window.is_usable
    assert RequestedCapability.FLIGHTS in merged.requested_capabilities
    assert RequestedCapability.HOTELS in merged.requested_capabilities


def test_component_result_serializes_machine_readable_outcome():
    result = ComponentResult(
        component="flights",
        status=ComponentStatus.BLOCKED_EXTERNAL,
        error_category=ErrorCategory.RATE_LIMIT,
        message="Provider temporarily unavailable",
        tools_called=["search_flights"],
    )

    payload = result.model_dump(mode="json")
    assert payload["status"] == "blocked_external"
    assert payload["error_category"] == "rate_limit"
    assert payload["tools_called"] == ["search_flights"]
