"""Integration tests — hit live external APIs.

Run with: pytest tests/test_integration.py -m integration
Skipped automatically when API keys are missing.
"""

import pytest

from tests.conftest import (
    skip_no_amadeus,
    skip_no_azure_openai,
    skip_no_exchangerate,
    skip_no_google_maps,
    skip_no_openweather,
)


@pytest.mark.integration
class TestWeatherIntegration:
    @skip_no_openweather
    async def test_live_weather_tokyo(self):
        from src.tools.weather import get_weather

        result = await get_weather.ainvoke({"city": "Tokyo", "days": 2})
        assert "Weather forecast for Tokyo" in result
        assert "°C" in result


@pytest.mark.integration
class TestCurrencyIntegration:
    @skip_no_exchangerate
    async def test_live_usd_to_jpy(self):
        from src.tools.currency import convert_currency

        result = await convert_currency.ainvoke({
            "from_currency": "USD",
            "to_currency": "JPY",
            "amount": 100,
        })
        assert "USD" in result
        assert "JPY" in result
        assert "Exchange rate" in result


@pytest.mark.integration
class TestSafetyIntegration:
    async def test_live_country_info(self):
        """REST Countries API requires no key — always runs."""
        from src.tools.safety import get_safety_info

        result = await get_safety_info.ainvoke({"country_name": "France"})
        assert "France" in result
        assert "Paris" in result
        assert "EUR" in result


@pytest.mark.integration
class TestFlightsIntegration:
    @skip_no_amadeus
    async def test_live_flight_search(self):
        from src.tools.flights import search_flights

        result = await search_flights.ainvoke({
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": "2026-09-15",
            "adults": 1,
        })
        # Should find flights or say none found — either is valid
        assert "JFK" in result or "No flights found" in result


@pytest.mark.integration
class TestHotelsIntegration:
    @skip_no_amadeus
    async def test_live_hotel_search(self):
        from src.tools.hotels import search_hotels

        result = await search_hotels.ainvoke({
            "city_code": "PAR",
            "check_in_date": "2026-09-15",
            "check_out_date": "2026-09-18",
            "adults": 1,
        })
        assert "PAR" in result or "No hotel offers found" in result


@pytest.mark.integration
class TestActivitiesIntegration:
    @skip_no_google_maps
    async def test_live_activities_search(self):
        from src.tools.activities import search_activities

        result = await search_activities.ainvoke({
            "city": "Tokyo, Japan",
            "category": "food",
            "query": "ramen",
            "limit": 3,
        })
        assert "Food in Tokyo" in result or "No food activities" in result


@pytest.mark.integration
class TestRAGIntegration:
    @skip_no_azure_openai
    def test_live_destination_guide_search(self):
        """Build real FAISS index with Azure OpenAI embeddings and search."""
        import src.tools.destination_rag as mod

        # Reset lazy init so this test gets a fresh store
        mod._vectorstore = None
        mod._initialised = False

        from src.tools.destination_rag import search_destination_guides

        result = search_destination_guides.invoke("Kyoto temples etiquette")
        assert "japan_guide.md" in result or "No destination guides" in result

        # Clean up
        mod._vectorstore = None
        mod._initialised = False
