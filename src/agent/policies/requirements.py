"""Scope-aware input requirements and localized clarification prompts."""

from __future__ import annotations

from collections.abc import Iterable
import re
import unicodedata

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

_CAPABILITY_EXTRA_ALIASES = {
    RequestedCapability.FLIGHTS: ("flight",),
    RequestedCapability.HOTELS: ("hotel", "accommodation", "noclegi", "alojamiento"),
    RequestedCapability.TRAVEL_READINESS: ("readiness",),
    RequestedCapability.RESTAURANTS: ("restaurant",),
    RequestedCapability.ACTIVITIES: ("activity",),
    RequestedCapability.TRANSPORTATION: ("transportation",),
    RequestedCapability.BUDGET: ("budget",),
    RequestedCapability.ITINERARY: ("itinerary",),
}

_SELECTED_ONLY_REPLIES = frozenset(
    {
        "continue",
        "continue as is",
        "current only",
        "no",
        "no thanks",
        "no thank you",
        "nie",
        "nie dziekuje",
        "kontynuuj",
        "no gracias",
        "continuar",
    }
)
_SELECTED_ONLY_PHRASES = (
    "current scope",
    "current services only",
    "selected services only",
    "only selected services",
    "no thanks",
    "no thank you",
    "no extras",
    "nothing else",
    "do not add",
    "dont add",
    "do not include",
    "keep it as is",
    "obecnym zakresie",
    "aktualnym zakresie",
    "tylko wybrane uslugi",
    "nic wiecej",
    "nie dodawaj",
    "alcance actual",
    "solo los servicios seleccionados",
    "sin extras",
    "nada mas",
    "no anadas",
    "no incluyas",
)
_INCLUDE_ALL_REPLIES = frozenset(
    {
        "all",
        "add all",
        "include all",
        "everything",
        "wszystkie",
        "dodaj wszystkie",
        "uwzglednij wszystkie",
        "wszystko",
        "todos",
        "anade todos",
        "incluye todos",
        "todo",
    }
)
_INCLUDE_ALL_PHRASES = (
    "add all",
    "include all",
    "all services",
    "include everything",
    "add everything",
    "dodaj wszystkie",
    "uwzglednij wszystkie",
    "wszystkie uslugi",
    "anade todos",
    "incluye todos",
    "todos los servicios",
)
_SINGLE_OFFER_AFFIRMATIONS = frozenset(
    {"yes", "yes please", "ok", "okay", "sure", "tak", "jasne", "si", "vale"}
)
_SINGLE_OFFER_ACCEPT_PHRASES = (
    "yes please",
    "yes include",
    "yes add",
    "please include it",
    "please add it",
    "tak dodaj",
    "si incluyelo",
)
_SINGLE_OFFER_DECLINE_PHRASES = (
    "dont need",
    "do not need",
    "dont want",
    "do not want",
    "skip it",
    "leave it out",
    "nie potrzebuje",
    "nie chce",
    "pomin",
    "no necesito",
    "no quiero",
    "omitelo",
)
_NEGATION_MARKERS = (
    "no ",
    "not ",
    "dont ",
    "do not ",
    "without ",
    "nie ",
    "bez ",
    "sin ",
)
_CAPABILITY_DECLINE_PREFIXES = (
    "no",
    "without",
    "do not add",
    "dont add",
    "do not include",
    "nie",
    "bez",
    "sin",
    "no anadas",
    "no incluyas",
)
_CAPABILITY_SELECTION_MARKERS = (
    "add",
    "include",
    "choose",
    "select",
    "want",
    "dodaj",
    "uwzglednij",
    "wybieram",
    "chce",
    "anade",
    "incluye",
    "elijo",
    "quiero",
)
_CAPABILITY_REPLY_FILLERS = frozenset({"and", "plus", "please", "i", "oraz", "y"})


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


def _normalise_scope_reply(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    without_marks = without_marks.translate(str.maketrans({"ł": "l"}))
    normalised = re.sub(r"[^a-z0-9]+", " ", without_marks).strip()
    return normalised.replace("don t", "dont")


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _capability_reply_aliases(capability: RequestedCapability) -> tuple[str, ...]:
    labels = (_CAPABILITY_LABELS[locale][capability] for locale in _CAPABILITY_LABELS)
    raw_aliases = (
        capability.value.replace("_", " "),
        *labels,
        *_CAPABILITY_EXTRA_ALIASES[capability],
    )
    return tuple(dict.fromkeys(_normalise_scope_reply(alias) for alias in raw_aliases))


def _explicitly_declines_capability(text: str, aliases: tuple[str, ...]) -> bool:
    return any(
        _contains_phrase(text, f"{prefix} {alias}")
        for prefix in _CAPABILITY_DECLINE_PREFIXES
        for alias in aliases
    )


def _explicitly_selects_capabilities(
    text: str,
    capabilities: list[RequestedCapability],
) -> bool:
    if any(_contains_phrase(text, marker) for marker in _CAPABILITY_SELECTION_MARKERS):
        return True

    remainder = f" {text} "
    aliases = {
        alias
        for capability in capabilities
        for alias in _capability_reply_aliases(capability)
    }
    for alias in sorted(aliases, key=len, reverse=True):
        remainder = re.sub(
            rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
            " ",
            remainder,
        )
    return set(remainder.split()).issubset(_CAPABILITY_REPLY_FILLERS)


def resolve_service_scope_reply(
    request: TripRequest,
    text: str,
) -> ServiceScopeDecision | None:
    """Convert an explicit free-text offer choice into a fingerprinted decision.

    This bounded parser supports Studio and other chat clients that cannot submit
    the structured control used by the web UI. Ambiguous replies remain unresolved.
    """
    offer = build_service_scope_offer(request)
    normalised = _normalise_scope_reply(text)
    if offer is None or not normalised:
        return None

    if normalised in _SELECTED_ONLY_REPLIES or any(
        _contains_phrase(normalised, phrase) for phrase in _SELECTED_ONLY_PHRASES
    ):
        return ServiceScopeDecision(
            action=ServiceScopeDecisionAction.SELECTED_ONLY,
            request_fingerprint=offer.request_fingerprint,
        )

    if len(offer.offered_capabilities) == 1 and any(
        _contains_phrase(normalised, phrase) for phrase in _SINGLE_OFFER_DECLINE_PHRASES
    ):
        return ServiceScopeDecision(
            action=ServiceScopeDecisionAction.SELECTED_ONLY,
            request_fingerprint=offer.request_fingerprint,
        )

    if normalised in _INCLUDE_ALL_REPLIES or any(
        _contains_phrase(normalised, phrase) for phrase in _INCLUDE_ALL_PHRASES
    ):
        return ServiceScopeDecision(
            action=ServiceScopeDecisionAction.INCLUDE_ALL,
            request_fingerprint=offer.request_fingerprint,
        )

    if len(offer.offered_capabilities) == 1 and (
        normalised in _SINGLE_OFFER_AFFIRMATIONS
        or any(
            _contains_phrase(normalised, phrase)
            for phrase in _SINGLE_OFFER_ACCEPT_PHRASES
        )
    ):
        return ServiceScopeDecision(
            action=ServiceScopeDecisionAction.INCLUDE_ALL,
            request_fingerprint=offer.request_fingerprint,
        )

    selected = [
        capability
        for capability in offer.offered_capabilities
        if any(
            _contains_phrase(normalised, alias)
            for alias in _capability_reply_aliases(capability)
        )
    ]
    if (
        selected
        and not any(marker in f"{normalised} " for marker in _NEGATION_MARKERS)
        and _explicitly_selects_capabilities(normalised, selected)
    ):
        return ServiceScopeDecision(
            action=ServiceScopeDecisionAction.INCLUDE_SELECTED,
            selected_capabilities=selected,
            request_fingerprint=offer.request_fingerprint,
        )
    if (
        len(offer.offered_capabilities) == 1
        and selected
        and _explicitly_declines_capability(
            normalised,
            _capability_reply_aliases(offer.offered_capabilities[0]),
        )
    ):
        return ServiceScopeDecision(
            action=ServiceScopeDecisionAction.SELECTED_ONLY,
            request_fingerprint=offer.request_fingerprint,
        )
    return None


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
