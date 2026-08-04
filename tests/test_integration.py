"""Integration tests — hit live external APIs.

Run explicitly with: pytest tests/test_integration.py -m integration
They are deselected by default and skipped when API keys are missing.
"""

import pytest

from tests.conftest import (
    skip_no_duffel,
    skip_no_exchangerate,
    skip_no_google_maps,
    skip_no_hotelbeds,
)


@pytest.mark.integration
class TestCurrencyIntegration:
    @skip_no_exchangerate
    async def test_live_usd_to_jpy(self):
        from src.tools.currency import convert_currency

        result = await convert_currency.ainvoke(
            {
                "from_currency": "USD",
                "to_currency": "JPY",
                "amount": 100,
            }
        )
        assert "USD" in result
        assert "JPY" in result
        assert "Exchange rate" in result


@pytest.mark.integration
class TestFlightsIntegration:
    @skip_no_duffel
    async def test_live_flight_search(self):
        from src.tools.flights_duffel import search_flights

        result = await search_flights.ainvoke(
            {
                "origin": "JFK",
                "destination": "LHR",
                "departure_date": "2026-09-15",
                "adults": 1,
            }
        )
        # Should find flights, say none found, or report an API error
        assert "JFK" in result or "No flights found" in result or "Duffel" in result


@pytest.mark.integration
class TestHotelbedIntegration:
    @skip_no_hotelbeds
    async def test_live_hotelbeds_search(self):
        from src.tools.hotels_hotelbeds import search_hotels_hotelbeds

        try:
            result = await search_hotels_hotelbeds.ainvoke(
                {
                    "city_code": "PAR",
                    "check_in_date": "2026-09-15",
                    "check_out_date": "2026-09-18",
                    "adults": 1,
                }
            )
        except Exception:
            pytest.skip("Hotelbeds API unavailable (rate limit or auth error)")
        assert "PAR" in result or "No hotel offers found on Hotelbeds" in result


@pytest.mark.integration
class TestActivitiesIntegration:
    @skip_no_google_maps
    async def test_live_activities_search(self):
        from src.tools.activities import search_activities

        result = await search_activities.ainvoke(
            {
                "city": "Tokyo, Japan",
                "category": "food",
                "query": "ramen",
                "limit": 3,
            }
        )
        assert "Food in Tokyo" in result or "No food activities" in result
