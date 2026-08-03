"""Open-Meteo adapter tests for exact-date readiness forecasts."""

from datetime import date, timedelta

import httpx
import respx

from src.readiness.weather import (
    FORECAST_URL,
    GEOCODING_URL,
    OpenMeteoWeatherProvider,
)
from src.models import DateWindow


@respx.mock
async def test_exact_forecast_is_normalized_and_source_preserves_provider_url():
    start = date.today() + timedelta(days=1)
    end = start + timedelta(days=1)
    respx.get(GEOCODING_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"latitude": 35.68, "longitude": 139.69}]},
        )
    )
    respx.get(FORECAST_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "daily": {
                    "time": [start.isoformat(), end.isoformat()],
                    "weather_code": [61, 2],
                    "temperature_2m_min": [20.1, 21.2],
                    "temperature_2m_max": [27.8, 29.0],
                    "precipitation_probability_max": [70, 15],
                }
            },
        )
    )
    provider = OpenMeteoWeatherProvider(max_retries=0)
    result = await provider.forecast(
        "Tokyo", DateWindow(exact_start=start, exact_end=end)
    )
    assert [item.condition for item in result.daily] == ["light rain", "partly cloudy"]
    assert result.daily[0].rain_probability_pct == 70
    assert result.source is not None
    assert result.source.domain == "open-meteo.com"
    assert result.source.url.startswith(FORECAST_URL)
    await provider.aclose()


@respx.mock
async def test_outside_forecast_horizon_returns_seasonal_limitation_without_http():
    start = date.today() + timedelta(days=30)
    provider = OpenMeteoWeatherProvider(max_retries=0)
    result = await provider.forecast(
        "Tokyo", DateWindow(exact_start=start, exact_end=start)
    )
    assert result.daily == []
    assert "outside Open-Meteo's forecast horizon" in result.limitations[0]
    assert not respx.calls
    await provider.aclose()


@respx.mock
async def test_partial_daily_arrays_use_safe_defaults_instead_of_crashing():
    start = date.today() + timedelta(days=1)
    respx.get(GEOCODING_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"latitude": 1, "longitude": 2}]},
        )
    )
    respx.get(FORECAST_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "daily": {
                    "time": [start.isoformat()],
                    "weather_code": [],
                    "temperature_2m_min": [],
                }
            },
        )
    )
    provider = OpenMeteoWeatherProvider(max_retries=0)
    result = await provider.forecast(
        "Test", DateWindow(exact_start=start, exact_end=start)
    )
    assert result.daily[0].condition == "clear sky"
    assert result.daily[0].temp_low_c == 0
    assert result.daily[0].temp_high_c == 0
    await provider.aclose()
