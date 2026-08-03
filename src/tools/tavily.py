"""Shared bounded Tavily HTTP transport, cache, and retry behavior."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, Field, field_validator

from custom_logging import AppLogger

logger = AppLogger(logger_name="tools.tavily", level="DEBUG")

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyProviderError(RuntimeError):
    """Base provider failure exposed to workflow outcome classification."""


class TavilyAuthenticationError(TavilyProviderError):
    pass


class TavilyRateLimitError(TavilyProviderError):
    pass


class TavilyTimeoutError(TavilyProviderError):
    pass


class TavilyTransientError(TavilyProviderError):
    pass


class TavilyQuery(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    search_topic: Literal["general", "news"] = "general"
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)

    @field_validator("include_domains", "exclude_domains")
    @classmethod
    def _normalise_domains(cls, domains: list[str]) -> list[str]:
        return sorted(
            {
                domain.strip().lower().removeprefix("www.")
                for domain in domains
                if domain and domain.strip()
            }
        )


class TavilySource(BaseModel):
    title: str = "Untitled"
    url: str
    domain: str
    snippet: str = ""
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    query: str
    published_at: str | None = None


@dataclass(frozen=True)
class TavilyAttempt:
    query: TavilyQuery
    sources: list[TavilySource] = field(default_factory=list)
    error: Exception | None = None


def normalize_url(url: str) -> str:
    """Normalize URLs for deterministic evidence deduplication."""
    parsed = urlsplit(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"
    path = parsed.path.rstrip("/") or "/"
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower() not in {"fbclid", "gclid"}
        )
    )
    return urlunsplit((parsed.scheme.lower() or "https", netloc, path, query, ""))


class TavilySearchProvider:
    """Generic Tavily client; domain trust policy belongs to each consumer."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        max_results: int = 5,
        concurrency: int = 4,
        max_retries: int = 3,
        cache_ttl_seconds: int = 6 * 3600,
        cache_max_size: int = 200,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = (
            os.environ.get("TAVILY_API_KEY", "") if api_key is None else api_key
        )
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results
        self.max_attempts = max(1, max_retries + 1)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache_max_size = cache_max_size
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._semaphore = asyncio.Semaphore(concurrency)
        self._cache: dict[str, tuple[float, list[TavilySource]]] = {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _cache_key(self, query: TavilyQuery) -> str:
        payload = {
            **query.model_dump(mode="json"),
            "max_results": self.max_results,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cached(self, query: TavilyQuery) -> list[TavilySource] | None:
        key = self._cache_key(query)
        entry = self._cache.get(key)
        if entry is None:
            return None
        created, sources = entry
        if time.monotonic() - created > self.cache_ttl_seconds:
            del self._cache[key]
            return None
        return [source.model_copy(deep=True) for source in sources]

    def _store(self, query: TavilyQuery, sources: list[TavilySource]) -> None:
        if len(self._cache) >= self.cache_max_size:
            oldest = min(self._cache, key=lambda key: self._cache[key][0])
            del self._cache[oldest]
        self._cache[self._cache_key(query)] = (
            time.monotonic(),
            [source.model_copy(deep=True) for source in sources],
        )

    async def search(self, query: TavilyQuery) -> list[TavilySource]:
        cached = self._cached(query)
        if cached is not None:
            logger.debug(f"Tavily cache hit: {query.query[:80]!r}")
            return cached
        if not self.api_key:
            raise TavilyAuthenticationError("TAVILY_API_KEY is not configured")

        payload: dict = {
            "api_key": self.api_key,
            "query": query.query,
            "topic": query.search_topic,
            "search_depth": "advanced",
            "max_results": self.max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        if query.include_domains:
            payload["include_domains"] = query.include_domains
        if query.exclude_domains:
            payload["exclude_domains"] = query.exclude_domains

        response: httpx.Response | None = None
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                async with self._semaphore:
                    response = await self._client.post(
                        TAVILY_SEARCH_URL,
                        json=payload,
                        timeout=self.timeout_seconds,
                    )
                if response.status_code in (401, 403):
                    raise TavilyAuthenticationError(
                        f"Tavily authentication failed (HTTP {response.status_code})"
                    )
                if response.status_code == 429:
                    last_error = TavilyRateLimitError("Tavily rate limit (HTTP 429)")
                elif response.status_code >= 500:
                    last_error = TavilyTransientError(
                        f"Tavily service error (HTTP {response.status_code})"
                    )
                else:
                    response.raise_for_status()
                    break
            except TavilyAuthenticationError:
                raise
            except httpx.TimeoutException as exc:
                last_error = TavilyTimeoutError(f"Tavily request timed out: {exc}")
            except httpx.NetworkError as exc:
                last_error = TavilyTransientError(f"Tavily network error: {exc}")
            except httpx.HTTPStatusError as exc:
                raise TavilyProviderError(
                    f"Tavily request rejected (HTTP {exc.response.status_code})"
                ) from exc

            if attempt < self.max_attempts - 1:
                await asyncio.sleep(2**attempt)
        else:
            if isinstance(last_error, (TavilyRateLimitError, TavilyTimeoutError)):
                raise last_error
            raise TavilyTransientError(str(last_error or "Tavily request failed"))

        assert response is not None
        sources: list[TavilySource] = []
        for result in response.json().get("results", []):
            url = str(result.get("url", "")).strip()
            if not url:
                continue
            normalized = normalize_url(url)
            domain = urlsplit(normalized).hostname or ""
            try:
                relevance = float(result.get("score", 0.0) or 0.0)
            except (TypeError, ValueError):
                relevance = 0.0
            sources.append(
                TavilySource(
                    title=str(result.get("title", "Untitled"))[:300],
                    url=normalized,
                    domain=domain,
                    snippet=str(result.get("content", "")).strip()[:1200],
                    relevance=max(0.0, min(1.0, relevance)),
                    query=query.query,
                    published_at=result.get("published_date"),
                )
            )
        self._store(query, sources)
        return sources

    async def search_many_isolated(
        self, queries: list[TavilyQuery]
    ) -> list[TavilyAttempt]:
        """Return every query outcome so one failure cannot erase other evidence."""
        results = await asyncio.gather(
            *(self.search(query) for query in queries),
            return_exceptions=True,
        )
        attempts: list[TavilyAttempt] = []
        for query, result in zip(queries, results, strict=True):
            if isinstance(result, BaseException):
                error = result if isinstance(result, Exception) else RuntimeError(str(result))
                attempts.append(TavilyAttempt(query=query, error=error))
            else:
                attempts.append(TavilyAttempt(query=query, sources=result))
        return attempts

    async def search_many(self, queries: list[TavilyQuery]) -> list[TavilySource]:
        """Convenience flat result for callers that do not need failure metadata."""
        attempts = await self.search_many_isolated(queries)
        by_url: dict[str, TavilySource] = {}
        for attempt in attempts:
            for source in attempt.sources:
                current = by_url.get(source.url)
                if current is None or source.relevance > current.relevance:
                    by_url[source.url] = source
        return sorted(by_url.values(), key=lambda item: item.relevance, reverse=True)
