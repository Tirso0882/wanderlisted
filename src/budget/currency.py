"""Typed exchange-rate boundary with per-process pair caching."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from time import monotonic

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import config as app_config


class ExchangeRateUnavailable(RuntimeError):
    """Raised when a required currency pair cannot be obtained safely."""


@dataclass(frozen=True, slots=True)
class ExchangeRateQuote:
    from_currency: str
    to_currency: str
    rate: Decimal
    provider: str
    observed_at: str


class ExchangeRateProvider:
    """Fetch each currency pair once per configurable cache window."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        cache_ttl_seconds: float | None = None,
    ) -> None:
        self._api_key = api_key
        self._cache_ttl_seconds = (
            float(cache_ttl_seconds)
            if cache_ttl_seconds is not None
            else float(
                app_config.get("budget", "exchange_rate_cache_ttl_seconds", 3600)
            )
        )
        self._cache: dict[tuple[str, str], tuple[ExchangeRateQuote, float]] = {}

    def remember_rate(self, quote: ExchangeRateQuote) -> None:
        """Seed a previously validated quote when resuming a budget review."""
        key = (quote.from_currency.strip().upper(), quote.to_currency.strip().upper())
        self._cache[key] = (quote, monotonic())

    async def get_rate(self, from_currency: str, to_currency: str) -> ExchangeRateQuote:
        source = from_currency.strip().upper()
        target = to_currency.strip().upper()
        if source == target:
            return ExchangeRateQuote(
                from_currency=source,
                to_currency=target,
                rate=Decimal("1"),
                provider="identity",
                observed_at=datetime.now(timezone.utc).isoformat(),
            )
        key = (source, target)
        cached = self._cache.get(key)
        if cached is not None:
            quote, cached_at = cached
            if monotonic() - cached_at <= self._cache_ttl_seconds:
                return quote
            self._cache.pop(key, None)

        api_key = self._api_key or os.environ.get("EXCHANGERATE_API_KEY", "")
        if not api_key:
            raise ExchangeRateUnavailable("EXCHANGERATE_API_KEY is not configured")

        timeout = float(app_config.get("timeouts", "currency", 10))
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{source}/{target}"
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, max=8),
                retry=retry_if_exception_type(
                    (httpx.TimeoutException, httpx.NetworkError)
                ),
                reraise=True,
            ):
                with attempt:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.get(url)
                        response.raise_for_status()
                        data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExchangeRateUnavailable(
                f"currency provider failed for {source}/{target}: {type(exc).__name__}"
            ) from exc

        if data.get("result") != "success" or data.get("conversion_rate") is None:
            raise ExchangeRateUnavailable(
                f"currency provider rejected {source}/{target}: "
                f"{data.get('error-type', 'unknown error')}"
            )
        quote = ExchangeRateQuote(
            from_currency=source,
            to_currency=target,
            rate=Decimal(str(data["conversion_rate"])),
            provider="exchangerate-api",
            observed_at=str(data.get("time_last_update_utc") or ""),
        )
        self.remember_rate(quote)
        return quote
