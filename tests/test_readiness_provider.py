"""Shared Tavily transport and readiness evidence-policy tests."""

from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from src.readiness import ReadinessEvidenceProvider, ReadinessQuery
from src.readiness.retrieval import official_domains_for
from src.tools.tavily import (
    TAVILY_SEARCH_URL,
    TavilyAttempt,
    TavilyAuthenticationError,
    TavilyProviderError,
    TavilyQuery,
    TavilyRateLimitError,
    TavilySearchProvider,
    TavilySource,
    TavilyTimeoutError,
    TavilyTransientError,
)


def _response(*results: dict) -> dict:
    return {"answer": "ignored generated answer", "results": list(results)}


@respx.mock
async def test_search_uses_raw_results_and_explicit_domains():
    route = respx.post(TAVILY_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json=_response(
                {
                    "title": "Official advisory",
                    "url": "https://travel.state.gov/example/",
                    "content": "Level 2 advisory.",
                    "score": 0.91,
                }
            ),
        )
    )
    provider = TavilySearchProvider(api_key="test", max_retries=0)
    sources = await provider.search(
        TavilyQuery(
            query="Japan travel advisory",
            include_domains=["travel.state.gov"],
        )
    )
    payload = route.calls[0].request.content.decode()
    assert '"include_answer":false' in payload
    assert "travel.state.gov" in payload
    assert sources[0].snippet == "Level 2 advisory."
    await provider.aclose()


@respx.mock
async def test_search_many_deduplicates_normalized_urls():
    respx.post(TAVILY_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json=_response(
                {
                    "title": "Same",
                    "url": "https://example.com/place/?utm_source=test",
                    "content": "Useful evidence",
                    "score": 0.8,
                }
            ),
        )
    )
    provider = TavilySearchProvider(api_key="test", max_retries=0)
    sources = await provider.search_many(
        [TavilyQuery(query="Tokyo culture"), TavilyQuery(query="Tokyo etiquette")]
    )
    assert len(sources) == 1
    assert sources[0].url == "https://example.com/place"
    await provider.aclose()


@respx.mock
async def test_cache_key_includes_search_parameters():
    route = respx.post(TAVILY_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json=_response(
                {
                    "title": "Result",
                    "url": "https://example.com/result",
                    "content": "Evidence",
                    "score": 0.7,
                }
            ),
        )
    )
    provider = TavilySearchProvider(api_key="test", max_retries=0)
    query = TavilyQuery(query="Tokyo events")
    await provider.search(query)
    await provider.search(query)
    await provider.search(query.model_copy(update={"search_topic": "news"}))
    assert route.call_count == 2
    await provider.aclose()


async def test_missing_key_is_authentication_error():
    provider = TavilySearchProvider(api_key="", max_retries=0)
    with pytest.raises(TavilyAuthenticationError):
        await provider.search(TavilyQuery(query="Tokyo travel"))
    await provider.aclose()


@respx.mock
async def test_authentication_error_is_not_retried():
    route = respx.post(TAVILY_SEARCH_URL).mock(return_value=httpx.Response(401))
    provider = TavilySearchProvider(api_key="bad", max_retries=3)
    with pytest.raises(TavilyAuthenticationError):
        await provider.search(TavilyQuery(query="Tokyo travel"))
    assert route.call_count == 1
    await provider.aclose()


@respx.mock
async def test_timeout_becomes_typed_error(monkeypatch):
    respx.post(TAVILY_SEARCH_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    monkeypatch.setattr("src.tools.tavily.asyncio.sleep", AsyncMock())
    provider = TavilySearchProvider(api_key="test", max_retries=1)
    with pytest.raises(TavilyTimeoutError):
        await provider.search(TavilyQuery(query="Tokyo travel"))
    await provider.aclose()


@respx.mock
async def test_empty_results_ignore_generated_answer():
    respx.post(TAVILY_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"answer": "unsupported", "results": []})
    )
    provider = TavilySearchProvider(api_key="test", max_retries=0)
    assert await provider.search(TavilyQuery(query="Unknown destination")) == []
    await provider.aclose()


@respx.mock
async def test_rate_limit_is_retried_then_classified(monkeypatch):
    route = respx.post(TAVILY_SEARCH_URL).mock(return_value=httpx.Response(429))
    monkeypatch.setattr("src.tools.tavily.asyncio.sleep", AsyncMock())
    provider = TavilySearchProvider(api_key="test", max_retries=2)
    with pytest.raises(TavilyRateLimitError):
        await provider.search(TavilyQuery(query="Tokyo travel"))
    assert route.call_count == 3
    await provider.aclose()


@respx.mock
async def test_server_error_is_retried(monkeypatch):
    route = respx.post(TAVILY_SEARCH_URL).mock(return_value=httpx.Response(503))
    monkeypatch.setattr("src.tools.tavily.asyncio.sleep", AsyncMock())
    provider = TavilySearchProvider(api_key="test", max_retries=1)
    with pytest.raises(TavilyTransientError):
        await provider.search(TavilyQuery(query="Tokyo travel"))
    assert route.call_count == 2
    await provider.aclose()


@respx.mock
async def test_network_error_is_retried(monkeypatch):
    route = respx.post(TAVILY_SEARCH_URL).mock(
        side_effect=[
            httpx.ConnectError("resolver failed"),
            httpx.Response(200, json=_response()),
        ]
    )
    monkeypatch.setattr("src.tools.tavily.asyncio.sleep", AsyncMock())
    provider = TavilySearchProvider(api_key="test", max_retries=1)
    assert await provider.search(TavilyQuery(query="Tokyo travel")) == []
    assert route.call_count == 2
    await provider.aclose()


@respx.mock
async def test_bad_request_is_not_retried():
    route = respx.post(TAVILY_SEARCH_URL).mock(return_value=httpx.Response(400))
    provider = TavilySearchProvider(api_key="test", max_retries=3)
    with pytest.raises(TavilyProviderError):
        await provider.search(TavilyQuery(query="Tokyo travel"))
    assert route.call_count == 1
    await provider.aclose()


def test_readiness_official_policy_has_no_permissive_entry_fallback():
    assert official_domains_for("visa") == []
    assert official_domains_for("safety", "Poland") == ["gov.pl"]
    policy = {"weather": ["meteo.pl"], "visa": ["immigration.gov.pl"]}
    assert "meteo.pl" in official_domains_for("weather", official_sources=policy)
    assert official_domains_for("visa", official_sources=policy) == [
        "immigration.gov.pl"
    ]


async def test_readiness_provider_tags_configured_authority_without_filtering_culture():
    query = ReadinessQuery(
        destination="tokyo",
        query="Tokyo etiquette",
        topic="culture",
    )
    transport = AsyncMock()
    transport.search_many_isolated.return_value = [
        TavilyAttempt(
            query=TavilyQuery(query=query.query),
            sources=[
                TavilySource(
                    title="Official guide",
                    url="https://gotokyo.org/customs",
                    domain="gotokyo.org",
                    query=query.query,
                )
            ],
        )
    ]
    provider = ReadinessEvidenceProvider(
        transport=transport,
        official_sources={"culture_authorities": ["gotokyo.org"]},
    )
    result = await provider.search_many([query])
    assert result.sources[0].is_official is True
    sent = transport.search_many_isolated.await_args.args[0][0]
    assert sent.include_domains == []


async def test_readiness_provider_does_not_cross_tag_official_topics():
    query = ReadinessQuery(
        destination="tokyo",
        query="Tokyo official advisory",
        topic="safety",
        include_domains=["travel.state.gov"],
    )
    transport = AsyncMock()
    transport.search_many_isolated.return_value = [
        TavilyAttempt(
            query=TavilyQuery(query=query.query),
            sources=[
                TavilySource(
                    title="Health authority, not an advisory authority",
                    url="https://who.int/tokyo",
                    domain="who.int",
                    query=query.query,
                )
            ],
        )
    ]

    result = await ReadinessEvidenceProvider(transport=transport).search_many([query])

    assert result.sources[0].is_official is False


async def test_readiness_provider_tracks_official_status_per_topic_scope():
    safety = ReadinessQuery(
        destination="tokyo",
        query="Tokyo official advisory",
        topic="safety",
        include_domains=["travel.state.gov"],
    )
    health = ReadinessQuery(
        destination="tokyo",
        query="Tokyo official health guidance",
        topic="health",
        include_domains=["who.int"],
    )
    shared = TavilySource(
        title="Shared result",
        url="https://who.int/tokyo",
        domain="who.int",
        query="Tokyo guidance",
    )
    transport = AsyncMock()
    transport.search_many_isolated.return_value = [
        TavilyAttempt(query=TavilyQuery(query=safety.query), sources=[shared]),
        TavilyAttempt(query=TavilyQuery(query=health.query), sources=[shared]),
    ]

    result = await ReadinessEvidenceProvider(transport=transport).search_many(
        [safety, health]
    )

    assert result.source_ids_for("tokyo", "safety") == ["S1"]
    assert result.official_source_ids_for("tokyo", "safety") == []
    assert result.official_source_ids_for("tokyo", "health") == ["S1"]


async def test_readiness_provider_isolates_one_failed_query():
    first = ReadinessQuery(
        destination="tokyo", query="Tokyo health", topic="health"
    )
    second = ReadinessQuery(
        destination="kyoto", query="Kyoto health", topic="health"
    )
    transport = AsyncMock()
    transport.search_many_isolated.return_value = [
        TavilyAttempt(
            query=TavilyQuery(query=first.query),
            error=TavilyTimeoutError("slow"),
        ),
        TavilyAttempt(
            query=TavilyQuery(query=second.query),
            sources=[
                TavilySource(
                    title="WHO",
                    url="https://who.int/kyoto",
                    domain="who.int",
                    query=second.query,
                )
            ],
        ),
    ]
    provider = ReadinessEvidenceProvider(transport=transport)
    result = await provider.search_many([first, second])
    assert len(result.sources) == 1
    assert result.source_ids_for("kyoto", "health") == ["S1"]
    assert result.failures[0].destination == "tokyo"
    assert result.failures[0].error_category == "timeout"
