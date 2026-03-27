"""Unit tests for safety info tool — mocked HTTP responses."""

import respx
from httpx import Response

from src.tools.safety import get_safety_info


_MOCK_COUNTRY_RESPONSE = [
    {
        "name": {"common": "Japan"},
        "capital": ["Tokyo"],
        "region": "Asia",
        "subregion": "Eastern Asia",
        "languages": {"jpn": "Japanese"},
        "currencies": {"JPY": {"name": "Japanese yen", "symbol": "¥"}},
        "population": 125800000,
        "timezones": ["UTC+09:00"],
    }
]


class TestSafetyMocked:
    @respx.mock
    async def test_returns_country_info(self):
        respx.get(url__regex=r"restcountries\.com").mock(
            return_value=Response(200, json=_MOCK_COUNTRY_RESPONSE)
        )

        result = await get_safety_info.ainvoke({"country_name": "Japan"})

        assert "Japan" in result
        assert "Tokyo" in result
        assert "Asia" in result
        assert "Japanese" in result

    @respx.mock
    async def test_includes_currency(self):
        respx.get(url__regex=r"restcountries\.com").mock(
            return_value=Response(200, json=_MOCK_COUNTRY_RESPONSE)
        )

        result = await get_safety_info.ainvoke({"country_name": "Japan"})

        assert "JPY" in result
        assert "¥" in result

    @respx.mock
    async def test_includes_travel_notes(self):
        respx.get(url__regex=r"restcountries\.com").mock(
            return_value=Response(200, json=_MOCK_COUNTRY_RESPONSE)
        )

        result = await get_safety_info.ainvoke({"country_name": "Japan"})

        assert "Travel Notes" in result
        assert "visa" in result.lower()

    @respx.mock
    async def test_empty_response(self):
        respx.get(url__regex=r"restcountries\.com").mock(
            return_value=Response(200, json=[])
        )

        result = await get_safety_info.ainvoke({"country_name": "Atlantis"})

        assert "No information found" in result
