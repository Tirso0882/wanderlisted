"""Deterministic requirement-policy tests across request scopes."""

import pytest

from src.agent.policies.requirements import (
    build_clarification_message,
    missing_required_fields,
    requested_agents,
)
from src.models import (
    DateWindow,
    ReadinessTopic,
    RequestScope,
    RequestedCapability,
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

    assert missing_required_fields(request) == ["date_window"]
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
    assert missing_required_fields(complete) == []


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
    assert missing_required_fields(request) == []
    assert requested_agents(request) == ["TravelReadinessAgent"]


def test_focused_entry_guidance_requires_passport_country():
    request = TripRequest(
        scope=RequestScope.FOCUSED,
        destinations=["japan"],
        requested_capabilities=["travel_readiness"],
        readiness_topics=["entry"],
    )

    assert missing_required_fields(request) == ["passport_country"]


def test_focused_hotel_search_requires_exact_stay_and_occupancy():
    request = TripRequest(
        scope=RequestScope.FOCUSED,
        destinations=["warszawa"],
        requested_capabilities=["hotels"],
    )
    assert missing_required_fields(request) == ["adults", "exact_stay_dates"]

    complete = request.model_copy(
        update={
            "travelers": TravelerParty(adults=2),
            "date_window": DateWindow(
                exact_start="2026-09-01",
                exact_end="2026-09-04",
            ),
        }
    )
    assert missing_required_fields(complete) == []
