"""Deterministic readiness intent, fingerprint, and bounded query planning."""

from __future__ import annotations

import hashlib
import json
from datetime import date

from src.models import ReadinessTopic, RequestScope, TripRequest
from src.readiness.models import (
    ReadinessEvidenceTopic,
    ReadinessIntent,
    ReadinessQuery,
    ReadinessResearchPlan,
)
from src.readiness.retrieval import (
    build_official_source_policy,
    official_domains_for,
)

_DISCOVERY_ONLY_TERMS = (
    "activity",
    "activities",
    "attraction",
    "event",
    "festival",
    "hidden gem",
    "restaurant",
    "things to do",
)

_CULTURE_EXCLUDED_DOMAINS = (
    "facebook.com",
    "quora.com",
    "reddit.com",
    "tripadvisor.com",
)

_CULTURE_QUERY_FOCUS = (
    (
        ("dining", "table manner", "chopstick", "tipping", "tip etiquette", "payment"),
        "dining etiquette table manners chopsticks tipping payment customs",
    ),
    (("greeting", "bow", "handshake"), "greeting bowing social etiquette"),
    (
        ("dress", "religious", "temple", "shrine", "mosque", "church"),
        "dress code religious-site etiquette",
    ),
    (
        ("train", "metro", "subway", "public transport"),
        "public transport etiquette",
    ),
    (
        ("pack", "packing", "bring", "wear"),
        "culture-based packing dress footwear preparation requirements",
    ),
)


def culture_query_focus(question: str) -> str:
    lowered = question.lower()
    focus = ["etiquette", "local customs"]
    for triggers, expansion in _CULTURE_QUERY_FOCUS:
        if any(trigger in lowered for trigger in triggers):
            focus.append(expansion)
    if len(focus) == 2:
        focus.append(
            "dining etiquette dress religious customs public transport manners"
        )
    return " ".join(focus)


def requested_topics(question: str, trip_request: TripRequest) -> set[ReadinessTopic]:
    if trip_request.readiness_topics:
        return set(trip_request.readiness_topics)
    if trip_request.scope == RequestScope.FULL_ITINERARY:
        return set(ReadinessTopic)
    lowered = question.lower()
    mapping = {
        ReadinessTopic.SAFETY: ("safe", "safety", "advisory", "risk"),
        ReadinessTopic.ENTRY: ("visa", "entry", "passport"),
        ReadinessTopic.HEALTH: ("health", "vaccine", "vaccination"),
        ReadinessTopic.WEATHER: ("weather", "forecast", "temperature", "rain"),
        ReadinessTopic.CULTURE: ("culture", "custom", "etiquette", "tipping"),
        ReadinessTopic.PRACTICAL: ("practical", "currency", "language", "emergency"),
        ReadinessTopic.PACKING: ("pack", "packing", "bring", "wear"),
    }
    selected = {
        topic
        for topic, words in mapping.items()
        if any(word in lowered for word in words)
    }
    if not selected and any(term in lowered for term in _DISCOVERY_ONLY_TERMS):
        return set()
    return selected or {ReadinessTopic.CULTURE, ReadinessTopic.PRACTICAL}


def readiness_request_fingerprint(
    trip_request: TripRequest, topics: set[ReadinessTopic]
) -> str:
    """Hash every readiness input whose change invalidates persisted results."""
    payload = {
        "destinations": sorted(trip_request.destinations),
        "passport_country": trip_request.passport_country.strip().lower(),
        "dates": trip_request.date_window.model_dump(mode="json"),
        "topics": sorted(topic.value for topic in topics),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class ReadinessPlanBuilder:
    """Allocate the fixed query budget fairly and with critical topics first."""

    def __init__(
        self,
        *,
        max_queries: int = 6,
        official_sources: dict | None = None,
    ) -> None:
        self.max_queries = max(1, max_queries)
        self.official_sources = build_official_source_policy(official_sources)

    def entry_domains(self, trip_request: TripRequest) -> list[str]:
        domains = set(self.official_sources["visa"])
        passport_domain = self.official_sources["safety_by_origin"].get(
            trip_request.passport_country.strip().lower()
        )
        if passport_domain:
            domains.add(passport_domain)
        return sorted(domains)

    def build(
        self,
        *,
        question: str,
        trip_request: TripRequest,
        topics: set[ReadinessTopic],
        seasonal_weather: set[str] | None = None,
    ) -> ReadinessResearchPlan:
        seasonal_weather = {item.lower() for item in (seasonal_weather or set())}
        destinations = list(trip_request.destinations)
        candidates: list[ReadinessQuery] = []

        # Topic-major iteration is round-robin across destinations. Every
        # destination gets each critical topic before optional topics consume
        # the remaining fixed budget.
        if ReadinessTopic.SAFETY in topics:
            for destination in destinations:
                candidates.append(
                    ReadinessQuery(
                        destination=destination,
                        query=(
                            f"{destination} current official travel advisory "
                            f"{date.today().isoformat()}"
                        ),
                        topic=ReadinessEvidenceTopic.SAFETY,
                        include_domains=official_domains_for(
                            ReadinessEvidenceTopic.SAFETY,
                            trip_request.origin_country
                            or trip_request.passport_country,
                            self.official_sources,
                        ),
                    )
                )

        if ReadinessTopic.ENTRY in topics and trip_request.passport_country:
            entry_domains = self.entry_domains(trip_request)
            if entry_domains:
                for destination in destinations:
                    candidates.append(
                        ReadinessQuery(
                            destination=destination,
                            query=(
                                f"{destination} official entry requirements for "
                                f"{trip_request.passport_country} passport holders"
                            ),
                            topic=ReadinessEvidenceTopic.ENTRY,
                            include_domains=entry_domains,
                        )
                    )

        if ReadinessTopic.HEALTH in topics:
            for destination in destinations:
                candidates.append(
                    ReadinessQuery(
                        destination=destination,
                        query=f"{destination} official travel health requirements",
                        topic=ReadinessEvidenceTopic.HEALTH,
                        include_domains=official_domains_for(
                            ReadinessEvidenceTopic.HEALTH,
                            official_sources=self.official_sources,
                        ),
                    )
                )

        if ReadinessTopic.WEATHER in topics:
            for destination in destinations:
                if destination.lower() in seasonal_weather:
                    candidates.append(
                        ReadinessQuery(
                            destination=destination,
                            query=(
                                f"{destination} official seasonal weather climate "
                                "travel dates"
                            ),
                            topic=ReadinessEvidenceTopic.WEATHER,
                            include_domains=official_domains_for(
                                ReadinessEvidenceTopic.WEATHER,
                                official_sources=self.official_sources,
                            ),
                        )
                    )

        if topics & {
            ReadinessTopic.CULTURE,
            ReadinessTopic.PRACTICAL,
            ReadinessTopic.PACKING,
        }:
            focus = culture_query_focus(question)
            for destination in destinations:
                candidates.append(
                    ReadinessQuery(
                        destination=destination,
                        query=(
                            f"{destination} official visitor {focus} "
                            "practical travel guidance"
                        ),
                        topic=ReadinessEvidenceTopic.CULTURE,
                        exclude_domains=list(_CULTURE_EXCLUDED_DOMAINS),
                    )
                )

        return ReadinessResearchPlan(
            destinations=destinations,
            intent=_intent_for(topics),
            requested_topics=sorted(topics, key=lambda topic: topic.value),
            queries=candidates[: self.max_queries],
        )


def _intent_for(topics: set[ReadinessTopic]) -> ReadinessIntent:
    if len(topics) != 1:
        return ReadinessIntent.COMPREHENSIVE
    return ReadinessIntent(next(iter(topics)).value)
