"""Readiness evidence policy layered over the shared Tavily transport."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field

from src.models import ErrorCategory, ReadinessTopic
from src.readiness.models import (
    ReadinessEvidenceTopic,
    ReadinessQuery,
    ReadinessSource,
)
from src.tools.tavily import (
    TavilyAuthenticationError,
    TavilyProviderError,
    TavilyQuery,
    TavilyRateLimitError,
    TavilySearchProvider,
    TavilyTimeoutError,
    TavilyTransientError,
)

OFFICIAL_DOMAINS: dict[ReadinessEvidenceTopic, tuple[str, ...]] = {
    ReadinessEvidenceTopic.SAFETY: ("travel.state.gov", "gov.uk"),
    ReadinessEvidenceTopic.WEATHER: ("worldweather.wmo.int",),
    ReadinessEvidenceTopic.HEALTH: ("who.int", "cdc.gov"),
}

_ADVISORY_DOMAIN_BY_ORIGIN = {
    "united states": "travel.state.gov",
    "usa": "travel.state.gov",
    "us": "travel.state.gov",
    "united kingdom": "gov.uk",
    "uk": "gov.uk",
    "great britain": "gov.uk",
    "poland": "gov.pl",
    "polska": "gov.pl",
    "colombia": "cancilleria.gov.co",
    "kolumbia": "cancilleria.gov.co",
}


class ReadinessQueryFailure(BaseModel):
    destination: str
    topic: ReadinessEvidenceTopic
    error_category: ErrorCategory = ErrorCategory.PROVIDER
    detail: str = ""


class ReadinessRetrieval(BaseModel):
    sources: list[ReadinessSource] = Field(default_factory=list)
    evidence_by_scope: dict[str, list[str]] = Field(default_factory=dict)
    official_evidence_by_scope: dict[str, list[str]] = Field(default_factory=dict)
    failures: list[ReadinessQueryFailure] = Field(default_factory=list)

    def source_ids_for(
        self,
        destination: str,
        topic: ReadinessTopic | ReadinessEvidenceTopic | str,
    ) -> list[str]:
        return self.evidence_by_scope.get(coverage_key(destination, topic), [])

    def official_source_ids_for(
        self,
        destination: str,
        topic: ReadinessTopic | ReadinessEvidenceTopic | str,
    ) -> list[str]:
        key = coverage_key(destination, topic)
        if key in self.official_evidence_by_scope:
            return self.official_evidence_by_scope[key]
        # Compatibility for injected providers in tests and adapters that
        # predate scope-specific trust metadata.
        official_ids = {source.id for source in self.sources if source.is_official}
        return [
            source_id
            for source_id in self.evidence_by_scope.get(key, [])
            if source_id in official_ids
        ]


def coverage_key(
    destination: str, topic: ReadinessTopic | ReadinessEvidenceTopic | str
) -> str:
    value = (
        topic.value
        if isinstance(topic, (ReadinessTopic, ReadinessEvidenceTopic))
        else topic
    )
    if value == ReadinessEvidenceTopic.ENTRY.value:
        value = ReadinessTopic.ENTRY.value
    return f"{destination.strip().lower()}:{value}"


def _normalise_domains(domains: Iterable[str]) -> list[str]:
    return sorted(
        {
            domain.strip().lower().removeprefix("www.")
            for domain in domains
            if domain and domain.strip()
        }
    )


def build_official_source_policy(overrides: dict | None = None) -> dict:
    """Merge configured authorities with conservative built-in defaults."""
    overrides = overrides or {}
    safety_by_origin = {
        **_ADVISORY_DOMAIN_BY_ORIGIN,
        **{
            str(origin).strip().lower(): str(domain).strip().lower()
            for origin, domain in overrides.get("safety_by_origin", {}).items()
            if origin and domain
        },
    }
    return {
        "safety_by_origin": safety_by_origin,
        "safety_fallback": _normalise_domains(
            overrides.get(
                "safety_fallback", OFFICIAL_DOMAINS[ReadinessEvidenceTopic.SAFETY]
            )
        ),
        "weather": _normalise_domains(
            [
                *OFFICIAL_DOMAINS[ReadinessEvidenceTopic.WEATHER],
                *overrides.get("weather", []),
            ]
        ),
        "health": _normalise_domains(
            [
                *OFFICIAL_DOMAINS[ReadinessEvidenceTopic.HEALTH],
                *overrides.get("health", []),
            ]
        ),
        "culture_authorities": _normalise_domains(
            overrides.get("culture_authorities", [])
        ),
        "visa": _normalise_domains(overrides.get("visa", [])),
        "emergency": _normalise_domains(overrides.get("emergency", [])),
    }


def official_domains_for(
    topic: ReadinessEvidenceTopic,
    origin_country: str = "",
    official_sources: dict | None = None,
) -> list[str]:
    topic = ReadinessEvidenceTopic(topic)
    policy = build_official_source_policy(official_sources)
    if topic == ReadinessEvidenceTopic.SAFETY:
        origin_domain = policy["safety_by_origin"].get(
            origin_country.strip().lower()
        )
        return [origin_domain] if origin_domain else list(policy["safety_fallback"])
    if topic == ReadinessEvidenceTopic.CULTURE:
        return []
    return list(policy.get(topic.value, ()))


def is_official_domain(domain: str, allowed: Iterable[str] | None = None) -> bool:
    normalised = domain.lower().removeprefix("www.")
    domains = set(
        allowed or (domain for values in OFFICIAL_DOMAINS.values() for domain in values)
    )
    return any(
        normalised == item or normalised.endswith(f".{item}") for item in domains
    )


def _error_category(error: Exception) -> ErrorCategory:
    if isinstance(error, TavilyAuthenticationError):
        return ErrorCategory.AUTHENTICATION
    if isinstance(error, TavilyRateLimitError):
        return ErrorCategory.RATE_LIMIT
    if isinstance(error, TavilyTimeoutError):
        return ErrorCategory.TIMEOUT
    return ErrorCategory.PROVIDER


class ReadinessEvidenceProvider:
    """Maps generic Tavily results into readiness-owned, policy-tagged evidence."""

    def __init__(
        self,
        *,
        official_sources: dict | None = None,
        transport: TavilySearchProvider | None = None,
        **transport_options,
    ) -> None:
        self.official_sources = build_official_source_policy(official_sources)
        self.transport = transport or TavilySearchProvider(**transport_options)

    async def aclose(self) -> None:
        await self.transport.aclose()

    async def search_many(
        self, queries: list[ReadinessQuery]
    ) -> ReadinessRetrieval:
        tavily_queries = [
            TavilyQuery(
                query=query.query,
                search_topic=query.search_topic,
                include_domains=query.include_domains,
                exclude_domains=query.exclude_domains,
            )
            for query in queries
        ]
        attempts = await self.transport.search_many_isolated(tavily_queries)

        by_url: dict[str, ReadinessSource] = {}
        scopes_by_url: dict[str, set[str]] = {}
        official_scopes_by_url: dict[str, set[str]] = {}
        failures: list[ReadinessQueryFailure] = []
        for query, attempt in zip(queries, attempts, strict=True):
            if attempt.error is not None:
                failures.append(
                    ReadinessQueryFailure(
                        destination=query.destination,
                        topic=query.topic,
                        error_category=_error_category(attempt.error),
                        detail=f"{type(attempt.error).__name__}: {attempt.error}",
                    )
                )
                continue
            scope = coverage_key(query.destination, query.topic)
            allowed_official_domains = list(query.include_domains)
            if query.topic == ReadinessEvidenceTopic.CULTURE:
                allowed_official_domains.extend(
                    self.official_sources["culture_authorities"]
                )
            for item in attempt.sources:
                source = ReadinessSource(
                    title=item.title,
                    url=item.url,
                    domain=item.domain,
                    snippet=item.snippet,
                    relevance=item.relevance,
                    query=query.query,
                    topic=query.topic,
                    is_official=(
                        bool(allowed_official_domains)
                        and is_official_domain(
                            item.domain, allowed_official_domains
                        )
                    ),
                    published_at=item.published_at,
                )
                current = by_url.get(item.url)
                if current is None:
                    by_url[item.url] = source
                elif source.relevance > current.relevance:
                    by_url[item.url] = source.model_copy(
                        update={"is_official": current.is_official or source.is_official}
                    )
                elif source.is_official and not current.is_official:
                    by_url[item.url] = current.model_copy(
                        update={"is_official": True}
                    )
                scopes_by_url.setdefault(item.url, set()).add(scope)
                if source.is_official:
                    official_scopes_by_url.setdefault(item.url, set()).add(scope)

        sources: list[ReadinessSource] = []
        evidence_by_scope: dict[str, list[str]] = {}
        official_evidence_by_scope: dict[str, list[str]] = {}
        for index, (url, source) in enumerate(by_url.items(), 1):
            source = source.model_copy(update={"id": f"S{index}"})
            sources.append(source)
            for scope in scopes_by_url[url]:
                evidence_by_scope.setdefault(scope, []).append(source.id)
                official_ids = official_evidence_by_scope.setdefault(scope, [])
                if scope in official_scopes_by_url.get(url, set()):
                    official_ids.append(source.id)
        return ReadinessRetrieval(
            sources=sources,
            evidence_by_scope=evidence_by_scope,
            official_evidence_by_scope=official_evidence_by_scope,
            failures=failures,
        )


__all__ = [
    "ReadinessEvidenceProvider",
    "ReadinessQueryFailure",
    "ReadinessRetrieval",
    "TavilyAuthenticationError",
    "TavilyProviderError",
    "TavilyRateLimitError",
    "TavilyTimeoutError",
    "TavilyTransientError",
    "build_official_source_policy",
    "coverage_key",
    "is_official_domain",
    "official_domains_for",
]
