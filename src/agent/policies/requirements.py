"""Scope-aware input requirements and localized clarification prompts."""

from __future__ import annotations

from src.models.trip_request import (
    RequestScope,
    RequestedCapability,
    TripRequest,
)

_FULL_CAPABILITIES = frozenset(
    {
        RequestedCapability.FLIGHTS,
        RequestedCapability.HOTELS,
        RequestedCapability.DESTINATION,
        RequestedCapability.RESTAURANTS,
        RequestedCapability.ACTIVITIES,
        RequestedCapability.TRANSPORTATION,
        RequestedCapability.BUDGET,
        RequestedCapability.ITINERARY,
    }
)

_CAPABILITY_TO_AGENT = {
    RequestedCapability.FLIGHTS: "FlightsAgent",
    RequestedCapability.HOTELS: "HotelsAgent",
    RequestedCapability.DESTINATION: "DestinationAgent",
    RequestedCapability.RESTAURANTS: "RestaurantsAgent",
    RequestedCapability.ACTIVITIES: "ActivitiesAgent",
    RequestedCapability.TRANSPORTATION: "TransportationAgent",
    RequestedCapability.BUDGET: "BudgetAgent",
    RequestedCapability.ITINERARY: "ItineraryAgent",
}

_AGENT_ORDER = (
    "FlightsAgent",
    "HotelsAgent",
    "DestinationAgent",
    "RestaurantsAgent",
    "ActivitiesAgent",
    "TransportationAgent",
    "BudgetAgent",
    "ItineraryAgent",
)


def effective_capabilities(request: TripRequest) -> frozenset[RequestedCapability]:
    """Return explicit capabilities or the full-plan defaults."""
    if request.requested_capabilities:
        return frozenset(request.requested_capabilities)
    if request.scope == RequestScope.FULL_ITINERARY:
        return _FULL_CAPABILITIES
    return frozenset()


def requested_agents(request: TripRequest) -> list[str]:
    """Map stable product capabilities to graph agent names in execution order."""
    selected = {
        _CAPABILITY_TO_AGENT[capability]
        for capability in effective_capabilities(request)
    }
    return [agent for agent in _AGENT_ORDER if agent in selected]


def missing_required_fields(request: TripRequest) -> list[str]:
    """Compute only fields required to execute the requested scope safely."""
    capabilities = effective_capabilities(request)
    missing: list[str] = []

    if request.scope == RequestScope.UNKNOWN:
        missing.append("request_scope")
        return missing

    if request.scope == RequestScope.FOCUSED and not capabilities:
        missing.append("requested_capability")
        return missing

    destination_capabilities = {
        RequestedCapability.FLIGHTS,
        RequestedCapability.HOTELS,
        RequestedCapability.DESTINATION,
        RequestedCapability.RESTAURANTS,
        RequestedCapability.ACTIVITIES,
        RequestedCapability.BUDGET,
        RequestedCapability.ITINERARY,
    }
    if capabilities & destination_capabilities and not request.destinations:
        missing.append("destinations")

    if RequestedCapability.FLIGHTS in capabilities:
        if not (request.origin_city or request.origin_airport):
            missing.append("origin_city")
        if not request.date_window.is_usable:
            missing.append("date_window")
        if request.travelers.adults is None:
            missing.append("adults")

    if RequestedCapability.HOTELS in capabilities:
        if request.travelers.adults is None and "adults" not in missing:
            missing.append("adults")
        if request.scope == RequestScope.FOCUSED:
            if not request.date_window.has_exact_stay:
                missing.append("exact_stay_dates")
        elif not request.date_window.is_usable and "date_window" not in missing:
            missing.append("date_window")

    if capabilities & {RequestedCapability.BUDGET, RequestedCapability.ITINERARY}:
        if not request.date_window.is_usable and "date_window" not in missing:
            missing.append("date_window")
        if request.travelers.adults is None and "adults" not in missing:
            missing.append("adults")

    return missing


_QUESTIONS = {
    "en": {
        "request_scope": "Do you want a complete itinerary or help with one specific topic?",
        "requested_capability": "Which travel topic should I help you with?",
        "destinations": "Which destination or cities should I plan for?",
        "origin_city": "Which city or airport will you depart from?",
        "date_window": "What exact dates or flexible travel window and trip length should I use?",
        "exact_stay_dates": "What are the hotel check-in and check-out dates?",
        "adults": "How many adults are traveling?",
    },
    "pl": {
        "request_scope": "Czy chcesz pełny plan podróży, czy informacje tylko o jednym temacie?",
        "requested_capability": "W jakim obszarze podróży mam Ci pomóc?",
        "destinations": "Jakie miejsce lub miasta mam zaplanować?",
        "origin_city": "Z jakiego miasta lub lotniska wylatujesz?",
        "date_window": "Jakie dokładne daty lub elastyczny okres i długość podróży mam przyjąć?",
        "exact_stay_dates": "Jakie są daty zameldowania i wymeldowania z hotelu?",
        "adults": "Ile osób dorosłych podróżuje?",
    },
}


def build_clarification_message(missing_fields: list[str], locale: str) -> str:
    """Build one concise, localized question covering all missing fields."""
    language = locale if locale in _QUESTIONS else "en"
    questions = [
        _QUESTIONS[language].get(field, _QUESTIONS["en"].get(field, field))
        for field in missing_fields
    ]
    if language == "pl":
        heading = "Zanim rozpocznę wyszukiwanie, potrzebuję jeszcze:"
    else:
        heading = "Before I start searching, I still need:"
    return heading + "\n" + "\n".join(f"- {question}" for question in questions)
