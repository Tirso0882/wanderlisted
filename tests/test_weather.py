"""Unit tests for weather tool — mocked HTTP responses via respx."""

import respx
from httpx import Response

from src.tools.weather import get_weather


# Sample OpenWeatherMap response (2 intervals → 1 day)
_MOCK_WEATHER_RESPONSE = {
    "list": [
        {
            "dt_txt": "2026-04-10 12:00:00",
            "main": {"temp": 18.5},
            "weather": [{"description": "clear sky"}],
            "pop": 0.1,
        },
        {
            "dt_txt": "2026-04-10 15:00:00",
            "main": {"temp": 22.3},
            "weather": [{"description": "clear sky"}],
            "pop": 0.05,
        },
        {
            "dt_txt": "2026-04-11 12:00:00",
            "main": {"temp": 15.0},
            "weather": [{"description": "broken clouds"}],
            "pop": 0.6,
        },
    ]
}


class TestWeatherMocked:
    @respx.mock
    async def test_returns_forecast_string(self, monkeypatch):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
        respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(
            return_value=Response(200, json=_MOCK_WEATHER_RESPONSE)
        )

        result = await get_weather.ainvoke({"city": "Tokyo", "days": 2})

        assert "Weather forecast for Tokyo" in result
        assert "2026-04-10" in result
        assert "clear sky" in result

    @respx.mock
    async def test_contains_temperature_range(self, monkeypatch):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
        respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(
            return_value=Response(200, json=_MOCK_WEATHER_RESPONSE)
        )

        result = await get_weather.ainvoke({"city": "Tokyo", "days": 2})

        # 18–22°C for the first day
        assert "18" in result or "19" in result
        assert "22" in result

    @respx.mock
    async def test_clamps_days_to_valid_range(self, monkeypatch):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
        route = respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(
            return_value=Response(200, json=_MOCK_WEATHER_RESPONSE)
        )

        await get_weather.ainvoke({"city": "Tokyo", "days": 99})

        # days clamped to 5, so cnt = 5 * 8 = 40
        assert route.calls[0].request.url.params["cnt"] == "40"
