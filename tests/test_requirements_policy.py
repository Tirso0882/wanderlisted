"""Deterministic requirement-policy tests across request scopes."""

from src.agent.policies.requirements import (
    build_clarification_message,
    missing_required_fields,
    requested_agents,
)
from src.models import DateWindow, RequestScope, TravelerParty, TripRequest


def test_polish_full_trip_requires_only_origin_and_adults():
    request = TripRequest(
        scope=RequestScope.FULL_ITINERARY,
        locale="pl",
        origin_country="Kolumbia",
        destinations=["krakow", "warszawa", "wroclaw", "gdansk"],
        date_window=DateWindow(
            earliest_start="2026-08-20",
            latest_end="2026-09-20",
            duration_days=14,
            flexible=True,
        ),
    )

    missing = missing_required_fields(request)

    assert missing == ["origin_city", "adults"]
    message = build_clarification_message(missing, request.locale)
    assert "Z jakiego miasta" in message
    assert "Ile osób dorosłych" in message
    assert requested_agents(request) == [
        "FlightsAgent",
        "HotelsAgent",
        "DestinationAgent",
        "RestaurantsAgent",
        "ActivitiesAgent",
        "TransportationAgent",
        "BudgetAgent",
        "ItineraryAgent",
    ]


def test_focused_destination_information_does_not_over_question():
    request = TripRequest(
        scope=RequestScope.FOCUSED,
        destinations=["krakow"],
        requested_capabilities=["destination"],
    )

    assert missing_required_fields(request) == []
    assert requested_agents(request) == ["DestinationAgent"]


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
