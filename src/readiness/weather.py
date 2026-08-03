"""Typed Open-Meteo forecasts for travel-readiness reports."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import urlencode

import httpx

from src.models import DateWindow, DayWeather
from src.readiness.models import ReadinessEvidenceTopic, ReadinessSource

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherProviderError(RuntimeError):
    """Open-Meteo request or response failure."""


@dataclass
class WeatherResult:
    destination: str
    daily: list[DayWeather] = field(default_factory=list)
    source: ReadinessSource | None = None
    limitations: list[str] = field(default_factory=list)


_WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "freezing fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    81: "rain showers",
    82: "heavy rain showers",
    95: "thunderstorms",
    96: "thunderstorms with hail",
    99: "severe thunderstorms with hail",
}


class OpenMeteoWeatherProvider:
    """Keyless Open-Meteo adapter with a bounded forecast horizon and cache."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10,
        max_retries: int = 2,
        forecast_horizon_days: int = 16,
        cache_ttl_seconds: int = 3600,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_retries + 1)
        self.forecast_horizon_days = max(1, min(forecast_horizon_days, 16))
        self.cache_ttl_seconds = cache_ttl_seconds
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._cache: dict[str, tuple[float, dict]] = {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, url: str, params: dict) -> dict:
        key = f"{url}?{urlencode(sorted(params.items()))}"
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] <= self.cache_ttl_seconds:
            return cached[1]

        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                response = await self._client.get(
                    url, params=params, timeout=self.timeout_seconds
                )
                response.raise_for_status()
                payload = response.json()
                self._cache[key] = (time.monotonic(), payload)
                return payload
            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
            ) as exc:
                last_error = exc
                if attempt < self.max_attempts - 1:
                    await asyncio.sleep(2**attempt)
        raise WeatherProviderError(f"Open-Meteo request failed: {last_error}")

    async def forecast(
        self, destination: str, date_window: DateWindow
    ) -> WeatherResult:
        start = date_window.exact_start
        end = date_window.exact_end
        today = date.today()
        horizon = today + timedelta(days=self.forecast_horizon_days)
        if not start or not end or start < today or end > horizon:
            return WeatherResult(
                destination=destination,
                limitations=[
                    "Exact forecast is outside Open-Meteo's forecast horizon; "
                    "seasonal guidance is shown instead."
                ],
            )

        geocoding = await self._get(
            GEOCODING_URL,
            {"name": destination, "count": 1, "language": "en", "format": "json"},
        )
        matches = geocoding.get("results") or []
        if not matches:
            return WeatherResult(
                destination=destination,
                limitations=[f"Open-Meteo could not resolve {destination}."],
            )
        location = matches[0]
        params = {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "timezone": "auto",
        }
        payload = await self._get(FORECAST_URL, params)
        daily = payload.get("daily") or {}
        dates = daily.get("time") or []
        weather_codes = daily.get("weather_code") or []
        lows = daily.get("temperature_2m_min") or []
        highs = daily.get("temperature_2m_max") or []
        rain = daily.get("precipitation_probability_max") or []

        def value(values: list, index: int, default=0):
            return (
                values[index]
                if index < len(values) and values[index] is not None
                else default
            )

        forecasts: list[DayWeather] = []
        for index, day in enumerate(dates):
            code = int(value(weather_codes, index) or 0)
            forecasts.append(
                DayWeather(
                    date=day,
                    condition=_WEATHER_CODES.get(code, f"weather code {code}"),
                    temp_low_c=float(value(lows, index)),
                    temp_high_c=float(value(highs, index)),
                    rain_probability_pct=int(value(rain, index) or 0),
                )
            )
        source_url = f"{FORECAST_URL}?{urlencode(params)}"
        return WeatherResult(
            destination=destination,
            daily=forecasts,
            source=ReadinessSource(
                title=f"Open-Meteo forecast for {destination}",
                url=source_url,
                domain="open-meteo.com",
                snippet="Typed daily forecast returned by Open-Meteo.",
                relevance=1.0,
                query=(
                    f"{destination} forecast {start.isoformat()} to {end.isoformat()}"
                ),
                topic=ReadinessEvidenceTopic.WEATHER,
                is_official=False,
            ),
        )
