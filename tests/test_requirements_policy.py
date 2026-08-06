"""Deterministic requirement-policy tests across request scopes."""

import pytest

from src.agent.policies.requirements import (
    apply_service_scope_decision,
    build_clarification_message,
    build_service_scope_offer,
    effective_capabilities,
    missing_required_fields,
    offered_capabilities,
    requested_agents,
)
from src.models import (
    DateWindow,
    ReadinessTopic,
    RequestScope,
    RequestedCapability,
    ServiceScopeDecision,
    TravelerParty,
    TripRequest,
)


def test_explicit_end_to_end_trip_requires_origin_passport_and_adults():
    request = TripRequest(
        scope=RequestScope.FULL_ITINERARY,
        locale="pl",
        origin_country="Kolumbia",
        destinations=["krakow", "warszawa", "wroclaw", "gdansk"],
        requested_capabilities=list(RequestedCapability),
        readiness_topics=[ReadinessTopic.ENTRY],
        date_window=DateWindow(
            earliest_start="2026-08-20",
            latest_end="2026-09-20",
            duration_days=14,
            flexible=True,
        ),
    )

    missing = missing_required_fields(request)

    assert missing == ["passport_country", "origin_city", "adults"]
    message = build_clarification_message(missing, request.locale)
    assert "Z jakiego miasta" in message
    assert "paszport" in message
    assert "Ile osób dorosłych" in message
    assert requested_agents(request) == [
        "FlightsAgent",
        "HotelsAgent",
        "TravelReadinessAgent",
        "RestaurantsAgent",
        "ActivitiesAgent",
        "TransportationAgent",
        "BudgetAgent",
        "ItineraryAgent",
    ]


def test_generic_city_break_defaults_to_destination_planning_only():
    request = TripRequest(
        scope=RequestScope.FULL_ITINERARY,
        destinations=["wroclaw"],
        date_window=DateWindow(exact_start="2026-10-08"),
    )

    assert missing_required_fields(request) == [
        "service_scope_confirmation",
        "date_window",
    ]
    assert requested_agents(request) == [
        "RestaurantsAgent",
        "ActivitiesAgent",
        "TransportationAgent",
        "ItineraryAgent",
    ]

    complete = request.model_copy(
        update={
            "date_window": DateWindow(
                exact_start="2026-10-08",
                exact_end="2026-10-10",
            )
        }
    )
    assert missing_required_fields(complete) == ["service_scope_confirmation"]


def test_named_full_trip_services_extend_defaults_and_offer_remaining_services():
    request = TripRequest(
        scope=RequestScope.FULL_ITINERARY,
        destinations=["gdansk"],
        requested_capabilities=["budget"],
        date_window=DateWindow(
            exact_start="2026-08-13",
            exact_end="2026-08-16",
        ),
        travelers=TravelerParty(adults=2, children=1),
        primary_transport_mode="drive",
    )

    assert effective_capabilities(request) == {
        RequestedCapability.RESTAURANTS,
        RequestedCapability.ACTIVITIES,
        RequestedCapability.TRANSPORTATION,
        RequestedCapability.BUDGET,
        RequestedCapability.ITINERARY,
    }
    assert RequestedCapability.FLIGHTS not in offered_capabilities(request)
    assert offered_capabilities(request) == {
        RequestedCapability.HOTELS,
        RequestedCapability.TRAVEL_READINESS,
    }
    assert missing_required_fields(request) == ["service_scope_confirmation"]


def test_explicit_selected_only_scope_runs_without_service_offer():
    request = TripRequest(
        scope=RequestScope.FOCUSED,
        destinations=["tokyo"],
        requested_capabilities=["flights", "hotels"],
        declined_capabilities=[
            "travel_readiness",
            "restaurants",
            "activities",
            "transportation",
            "budget",
            "itinerary",
        ],
        capability_scope_confirmed=True,
        capability_scope_exclusive=True,
        date_window=DateWindow(
            exact_start="2026-10-08",
            exact_end="2026-10-10",
        ),
        travelers=TravelerParty(adults=2),
        origin_city="wroclaw",
    )

    assert offered_capabilities(request) == set()
    assert requested_agents(request) == ["FlightsAgent", "HotelsAgent"]
    assert missing_required_fields(request) == []


def test_service_scope_decision_supports_selective_additions():
    request = TripRequest(
        scope=RequestScope.FOCUSED,
        destinations=["tokyo"],
        requested_capabilities=["flights", "hotels"],
        date_window=DateWindow(
            exact_start="2026-10-08",
            exact_end="2026-10-10",
        ),
        travelers=TravelerParty(adults=2),
        origin_city="wroclaw",
    )
    offer = build_service_scope_offer(request)
    assert offer is not None

    resolved = apply_service_scope_decision(
        request,
        ServiceScopeDecision(
            action="include_selected",
            selected_capabilities=["restaurants", "activities"],
            request_fingerprint=offer.request_fingerprint,
        ),
    )

    assert resolved.capability_scope_confirmed is True
    assert set(resolved.requested_capabilities) == {
        RequestedCapability.FLIGHTS,
        RequestedCapability.HOTELS,
        RequestedCapability.RESTAURANTS,
        RequestedCapability.ACTIVITIES,
    }
    assert set(resolved.declined_capabilities) == {
        RequestedCapability.TRAVEL_READINESS,
        RequestedCapability.TRANSPORTATION,
        RequestedCapability.BUDGET,
        RequestedCapability.ITINERARY,
    }
    assert offered_capabilities(resolved) == set()


def test_explicit_only_services_override_accidental_full_itinerary_scope():
    request = TripRequest(
        scope=RequestScope.FULL_ITINERARY,
        destinations=["tokyo"],
        requested_capabilities=["flights", "hotels"],
        capability_scope_confirmed=True,
        capability_scope_exclusive=True,
    )

    assert effective_capabilities(request) == {
        RequestedCapability.FLIGHTS,
        RequestedCapability.HOTELS,
    }
    assert requested_agents(request) == ["FlightsAgent", "HotelsAgent"]


def test_broad_road_trip_goal_requires_exact_route_scope_before_search():
    request = TripRequest(
        scope=RequestScope.FULL_ITINERARY,
        origin_city="wroclaw",
        route_goal="poland along the german border to the baltic sea",
        requested_capabilities=["budget"],
        capability_scope_confirmed=True,
        primary_transport_mode="drive",
        date_window=DateWindow(
            exact_start="2026-08-13",
            exact_end="2026-08-16",
        ),
        travelers=TravelerParty(adults=2, children=1),
    )

    assert missing_required_fields(request) == ["route_scope_confirmation"]
    message = build_clarification_message(
        missing_required_fields(request), request.locale
    )
    assert "endpoint" in message
    assert "overnight cities" in message


def test_broad_road_trip_can_use_explicitly_delegated_city_proposal():
    request = TripRequest(
        scope=RequestScope.FULL_ITINERARY,
        origin_city="wroclaw",
        route_goal="poland along the german border to the baltic sea",
        overnight_cities=["zielona gora", "szczecin", "pobierowo"],
        route_scope_delegated=True,
        requested_capabilities=["budget"],
        capability_scope_confirmed=True,
        primary_transport_mode="drive",
        date_window=DateWindow(
            exact_start="2026-08-13",
            exact_end="2026-08-16",
        ),
        travelers=TravelerParty(adults=2, children=1),
    )

    assert request.route_scope_resolved is True
    assert missing_required_fields(request) == []


def test_route_delegation_without_concrete_cities_still_fails_closed():
    request = TripRequest(
        scope=RequestScope.FULL_ITINERARY,
        route_goal="to the baltic coast",
        route_scope_delegated=True,
        capability_scope_confirmed=True,
        date_window=DateWindow(
            exact_start="2026-08-13",
            exact_end="2026-08-16",
        ),
    )

    assert request.route_scope_delegated is False
    assert request.route_scope_resolved is False
    assert missing_required_fields(request) == ["route_scope_confirmation"]


def test_hotel_search_with_child_requires_each_child_age():
    request = TripRequest(
        scope=RequestScope.FOCUSED,
        destinations=["gdansk"],
        requested_capabilities=["hotels"],
        capability_scope_confirmed=True,
        date_window=DateWindow(
            exact_start="2026-08-13",
            exact_end="2026-08-16",
        ),
        travelers=TravelerParty(adults=2, children=1),
    )

    assert missing_required_fields(request) == ["child_ages"]


def test_legacy_destination_capability_is_rejected():
    with pytest.raises(ValueError):
        TripRequest(
            scope=RequestScope.FOCUSED,
            destinations=["krakow"],
            requested_capabilities=["destination"],
        )

    request = TripRequest(
        scope=RequestScope.FOCUSED,
        destinations=["krakow"],
        requested_capabilities=["travel_readiness"],
    )
    assert missing_required_fields(request) == ["service_scope_confirmation"]
    assert requested_agents(request) == ["TravelReadinessAgent"]


def test_focused_entry_guidance_requires_passport_country():
    request = TripRequest(
        scope=RequestScope.FOCUSED,
        destinations=["japan"],
        requested_capabilities=["travel_readiness"],
        readiness_topics=["entry"],
    )

    assert missing_required_fields(request) == [
        "service_scope_confirmation",
        "passport_country",
    ]


def test_focused_hotel_search_requires_exact_stay_and_occupancy():
    request = TripRequest(
        scope=RequestScope.FOCUSED,
        destinations=["warszawa"],
        requested_capabilities=["hotels"],
    )
    assert missing_required_fields(request) == [
        "service_scope_confirmation",
        "adults",
        "exact_stay_dates",
    ]

    complete = request.model_copy(
        update={
            "travelers": TravelerParty(adults=2),
            "date_window": DateWindow(
                exact_start="2026-09-01",
                exact_end="2026-09-04",
            ),
        }
    )
    assert missing_required_fields(complete) == ["service_scope_confirmation"]
