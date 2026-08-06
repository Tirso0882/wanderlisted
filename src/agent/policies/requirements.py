"""Scope-aware input requirements and localized clarification prompts."""

from __future__ import annotations

from collections.abc import Iterable

from src.models.trip_request import (
    ReadinessTopic,
    RequestScope,
    RequestedCapability,
    ServiceScopeDecision,
    ServiceScopeDecisionAction,
    ServiceScopeOffer,
    TripRequest,
    TripRequestPatch,
    merge_trip_request,
    service_scope_fingerprint,
)

# A generic request to plan a trip is consent to build the destination plan,
# not to search bookable inventory or research entry requirements. Those
# capability owners have additional critical inputs and are activated only
# when intake extracts them explicitly.
_DEFAULT_PLANNING_CAPABILITIES = frozenset(
    {
        RequestedCapability.RESTAURANTS,
        RequestedCapability.ACTIVITIES,
        RequestedCapability.TRANSPORTATION,
        RequestedCapability.ITINERARY,
    }
)

_ALL_CAPABILITIES = frozenset(RequestedCapability)

_CAPABILITY_TO_AGENT = {
    RequestedCapability.FLIGHTS: "FlightsAgent",
    RequestedCapability.HOTELS: "HotelsAgent",
    RequestedCapability.TRAVEL_READINESS: "TravelReadinessAgent",
    RequestedCapability.RESTAURANTS: "RestaurantsAgent",
    RequestedCapability.ACTIVITIES: "ActivitiesAgent",
    RequestedCapability.TRANSPORTATION: "TransportationAgent",
    RequestedCapability.BUDGET: "BudgetAgent",
    RequestedCapability.ITINERARY: "ItineraryAgent",
}

_AGENT_ORDER = (
    "FlightsAgent",
    "HotelsAgent",
    "TravelReadinessAgent",
    "RestaurantsAgent",
    "ActivitiesAgent",
    "TransportationAgent",
    "BudgetAgent",
    "ItineraryAgent",
)

_CAPABILITY_ORDER = tuple(RequestedCapability)

_CAPABILITY_LABELS = {
    "en": {
        RequestedCapability.FLIGHTS: "flights",
        RequestedCapability.HOTELS: "hotels",
        RequestedCapability.TRAVEL_READINESS: "travel readiness",
        RequestedCapability.RESTAURANTS: "restaurants",
        RequestedCapability.ACTIVITIES: "activities",
        RequestedCapability.TRANSPORTATION: "local transportation",
        RequestedCapability.BUDGET: "budget planning",
        RequestedCapability.ITINERARY: "a day-by-day itinerary",
    },
    "pl": {
        RequestedCapability.FLIGHTS: "loty",
        RequestedCapability.HOTELS: "hotele",
        RequestedCapability.TRAVEL_READINESS: "przygotowanie do podróży",
        RequestedCapability.RESTAURANTS: "restauracje",
        RequestedCapability.ACTIVITIES: "atrakcje",
        RequestedCapability.TRANSPORTATION: "transport lokalny",
        RequestedCapability.BUDGET: "plan budżetu",
        RequestedCapability.ITINERARY: "plan dzień po dniu",
    },
    "es": {
        RequestedCapability.FLIGHTS: "vuelos",
        RequestedCapability.HOTELS: "hoteles",
        RequestedCapability.TRAVEL_READINESS: "preparación para el viaje",
        RequestedCapability.RESTAURANTS: "restaurantes",
        RequestedCapability.ACTIVITIES: "actividades",
        RequestedCapability.TRANSPORTATION: "transporte local",
        RequestedCapability.BUDGET: "planificación del presupuesto",
        RequestedCapability.ITINERARY: "itinerario día a día",
    },
}


def _ordered_capabilities(
    capabilities: Iterable[RequestedCapability],
) -> list[RequestedCapability]:
    selected = set(capabilities)
    return [capability for capability in _CAPABILITY_ORDER if capability in selected]


def effective_capabilities(request: TripRequest) -> frozenset[RequestedCapability]:
    """Return the confirmed execution set without treating mentions as exclusive."""
    selected = set(request.requested_capabilities)
    if (
        request.scope == RequestScope.FULL_ITINERARY
        and not request.capability_scope_exclusive
    ):
        selected.update(_DEFAULT_PLANNING_CAPABILITIES)
    selected.difference_update(request.declined_capabilities)
    return frozenset(selected)


def offered_capabilities(request: TripRequest) -> frozenset[RequestedCapability]:
    """Return applicable unselected services that require traveler confirmation."""
    if request.capability_scope_confirmed or request.scope == RequestScope.UNKNOWN:
        return frozenset()
    if request.scope == RequestScope.FOCUSED and not request.requested_capabilities:
        return frozenset()

    offered = set(_ALL_CAPABILITIES - effective_capabilities(request))
    offered.difference_update(request.declined_capabilities)
    if (
        request.primary_transport_mode is not None
        and str(request.primary_transport_mode) == "drive"
    ):
        offered.discard(RequestedCapability.FLIGHTS)

    window = request.date_window
    known_day_trip = window.duration_days == 1 or (
        window.exact_start is not None
        and window.exact_end is not None
        and window.exact_start == window.exact_end
    )
    if known_day_trip:
        offered.discard(RequestedCapability.HOTELS)
    return frozenset(offered)


def build_service_scope_offer(request: TripRequest) -> ServiceScopeOffer | None:
    """Build the structured pending offer consumed by API and frontend clients."""
    offered = offered_capabilities(request)
    if not offered:
        return None
    return ServiceScopeOffer(
        selected_capabilities=_ordered_capabilities(effective_capabilities(request)),
        offered_capabilities=_ordered_capabilities(offered),
        request_fingerprint=service_scope_fingerprint(request),
    )


def apply_service_scope_decision(
    request: TripRequest,
    decision: ServiceScopeDecision,
) -> TripRequest:
    """Apply one current offer decision without invoking a model."""
    offer = build_service_scope_offer(request)
    if offer is None or decision.request_fingerprint != offer.request_fingerprint:
        raise ValueError("service scope offer is stale")

    offered = set(offer.offered_capabilities)
    selected: set[RequestedCapability] = set(effective_capabilities(request))
    declined: set[RequestedCapability] = set()
    if decision.action == ServiceScopeDecisionAction.INCLUDE_ALL:
        selected.update(offered)
    elif decision.action == ServiceScopeDecisionAction.SELECTED_ONLY:
        declined = offered
    else:
        additions = set(decision.selected_capabilities)
        if not additions.issubset(offered):
            raise ValueError("selected capability was not present in the offer")
        selected.update(additions)
        declined = offered - additions

    return merge_trip_request(
        request,
        TripRequestPatch(
            requested_capabilities=_ordered_capabilities(selected),
            declined_capabilities=_ordered_capabilities(declined),
            capability_scope_confirmed=True,
            capability_scope_exclusive=True,
        ),
    )


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

    if offered_capabilities(request):
        missing.append("service_scope_confirmation")

    if request.route_goal and not request.route_scope_resolved:
        missing.append("route_scope_confirmation")

    destination_capabilities = {
        RequestedCapability.FLIGHTS,
        RequestedCapability.HOTELS,
        RequestedCapability.TRAVEL_READINESS,
        RequestedCapability.RESTAURANTS,
        RequestedCapability.ACTIVITIES,
        RequestedCapability.BUDGET,
        RequestedCapability.ITINERARY,
    }
    if (
        capabilities & destination_capabilities
        and not request.destinations
        and "route_scope_confirmation" not in missing
    ):
        missing.append("destinations")

    readiness_requested = RequestedCapability.TRAVEL_READINESS in capabilities
    entry_requested = (
        request.scope == RequestScope.FULL_ITINERARY
        or ReadinessTopic.ENTRY in request.readiness_topics
    )
    if readiness_requested and entry_requested and not request.passport_country:
        missing.append("passport_country")

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
        if (
            request.travelers.children > 0
            and len(request.travelers.child_ages) != request.travelers.children
        ):
            missing.append("child_ages")
        if request.scope == RequestScope.FOCUSED:
            if not request.date_window.has_exact_stay:
                missing.append("exact_stay_dates")
        elif not request.date_window.is_usable and "date_window" not in missing:
            missing.append("date_window")

    if RequestedCapability.BUDGET in capabilities:
        if not request.date_window.is_usable and "date_window" not in missing:
            missing.append("date_window")
        if request.travelers.adults is None and "adults" not in missing:
            missing.append("adults")

    if RequestedCapability.ITINERARY in capabilities:
        if not request.date_window.is_usable and "date_window" not in missing:
            missing.append("date_window")

    return missing


_QUESTIONS = {
    "en": {
        "request_scope": "Do you want a complete itinerary or help with one specific topic?",
        "requested_capability": "Which travel topic should I help you with?",
        "service_scope_confirmation": "Should I include the other applicable travel services, or continue only with the services already selected?",
        "route_scope_confirmation": "Which exact endpoint and overnight cities should I use for this route?",
        "destinations": "Which destination or cities should I plan for?",
        "origin_city": "Which city or airport will you depart from?",
        "passport_country": "Which country issued your passport?",
        "date_window": "What exact dates or flexible travel window and trip length should I use?",
        "exact_stay_dates": "What are the hotel check-in and check-out dates?",
        "adults": "How many adults are traveling?",
        "child_ages": "What is the age of each child traveling?",
    },
    "pl": {
        "request_scope": "Czy chcesz pełny plan podróży, czy informacje tylko o jednym temacie?",
        "requested_capability": "W jakim obszarze podróży mam Ci pomóc?",
        "service_scope_confirmation": "Czy mam uwzględnić pozostałe pasujące usługi, czy kontynuować tylko z już wybranymi?",
        "route_scope_confirmation": "Jaki dokładny punkt końcowy i miasta noclegowe mam przyjąć na tej trasie?",
        "destinations": "Jakie miejsce lub miasta mam zaplanować?",
        "origin_city": "Z jakiego miasta lub lotniska wylatujesz?",
        "passport_country": "Który kraj wydał Twój paszport?",
        "date_window": "Jakie dokładne daty lub elastyczny okres i długość podróży mam przyjąć?",
        "exact_stay_dates": "Jakie są daty zameldowania i wymeldowania z hotelu?",
        "adults": "Ile osób dorosłych podróżuje?",
        "child_ages": "Ile lat ma każde podróżujące dziecko?",
    },
    "es": {
        "request_scope": "¿Quieres un itinerario completo o ayuda con un tema específico?",
        "requested_capability": "¿Con qué aspecto del viaje quieres ayuda?",
        "service_scope_confirmation": "¿Debo incluir los demás servicios aplicables o continuar solo con los servicios ya seleccionados?",
        "route_scope_confirmation": "¿Qué destino final y qué ciudades para pernoctar debo usar en esta ruta?",
        "destinations": "¿Qué destino o ciudades debo planificar?",
        "origin_city": "¿Desde qué ciudad o aeropuerto saldrás?",
        "passport_country": "¿Qué país expidió tu pasaporte?",
        "date_window": "¿Qué fechas exactas o intervalo flexible y duración debo usar?",
        "exact_stay_dates": "¿Cuáles son las fechas de entrada y salida del hotel?",
        "adults": "¿Cuántos adultos viajan?",
        "child_ages": "¿Qué edad tiene cada niño que viaja?",
    },
}


def build_clarification_message(
    missing_fields: list[str],
    locale: str,
    offered: Iterable[RequestedCapability] = (),
) -> str:
    """Build one concise, localized question covering all missing fields."""
    language = locale if locale in _QUESTIONS else "en"
    questions = [
        _QUESTIONS[language].get(field, _QUESTIONS["en"].get(field, field))
        for field in missing_fields
    ]
    offered_list = _ordered_capabilities(offered)
    if "service_scope_confirmation" in missing_fields and offered_list:
        labels = ", ".join(_CAPABILITY_LABELS[language][item] for item in offered_list)
        service_question = (
            f"Mogę też uwzględnić: {labels}. Dodać wszystkie, wybrane, czy pozostać przy obecnym zakresie?"
            if language == "pl"
            else f"También puedo incluir: {labels}. ¿Añado todos, eliges algunos o continúo solo con el alcance actual?"
            if language == "es"
            else f"I can also include: {labels}. Add all, choose some, or continue with the current scope only?"
        )
        questions[missing_fields.index("service_scope_confirmation")] = service_question
    if language == "pl":
        heading = "Zanim rozpocznę wyszukiwanie, potrzebuję jeszcze:"
    elif language == "es":
        heading = "Antes de empezar la búsqueda, todavía necesito:"
    else:
        heading = "Before I start searching, I still need:"
    return heading + "\n" + "\n".join(f"- {question}" for question in questions)
