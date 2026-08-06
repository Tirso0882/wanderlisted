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
            capability_scope_confirmed=True,
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
    assert merged.capability_scope_confirmed is True


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


def test_confirmed_overnight_cities_become_canonical_destinations():
    request = merge_trip_request(
        None,
        TripRequestPatch(
            scope=RequestScope.FULL_ITINERARY,
            route_goal="Wroclaw to the Baltic coast",
            overnight_cities=["Zielona Gora", "Szczecin", "Swinoujscie"],
            route_scope_confirmed=True,
            requested_capabilities=[RequestedCapability.ITINERARY],
            capability_scope_confirmed=True,
        ),
    )

    assert request.destinations == ["zielona gora", "szczecin", "swinoujscie"]


def test_delegated_overnight_cities_become_canonical_destinations():
    request = merge_trip_request(
        None,
        TripRequestPatch(
            scope=RequestScope.FULL_ITINERARY,
            route_goal="Wroclaw to the Baltic coast",
            overnight_cities=["Zielona Gora", "Szczecin", "Pobierowo"],
            route_scope_delegated=True,
            requested_capabilities=[RequestedCapability.ITINERARY],
            capability_scope_confirmed=True,
        ),
    )

    assert request.route_scope_resolved is True
    assert request.route_scope_confirmed is False
    assert request.route_scope_delegated is True
    assert request.destinations == ["zielona gora", "szczecin", "pobierowo"]


def test_route_change_resets_previous_delegated_resolution():
    delegated = merge_trip_request(
        None,
        TripRequestPatch(
            scope=RequestScope.FULL_ITINERARY,
            route_goal="Wroclaw to the Baltic coast",
            overnight_cities=["Szczecin", "Pobierowo"],
            route_scope_delegated=True,
        ),
    )

    changed = merge_trip_request(
        delegated,
        TripRequestPatch(route_goal="Wroclaw to the Czech border"),
    )

    assert changed.route_scope_confirmed is False
    assert changed.route_scope_delegated is False
    assert changed.route_scope_resolved is False


def test_broad_sea_destination_is_recovered_as_unconfirmed_route_goal():
    request = merge_trip_request(
        None,
        TripRequestPatch(
            scope=RequestScope.FULL_ITINERARY,
            destinations=["Baltic Sea"],
            requested_capabilities=[RequestedCapability.ITINERARY],
            capability_scope_confirmed=True,
        ),
    )

    assert request.destinations == []
    assert request.route_goal == "baltic sea"
    assert request.route_scope_confirmed is False
