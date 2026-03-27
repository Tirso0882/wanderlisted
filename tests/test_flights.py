"""Unit tests for flight search tool — mocked Amadeus API responses."""

import respx
from httpx import Response

from src.tools.flights import search_flights, _token_cache


_MOCK_TOKEN_RESPONSE = {
    "access_token": "mock-token-12345",
    "token_type": "Bearer",
    "expires_in": 1799,
}

_MOCK_FLIGHTS_RESPONSE = {
    "data": [
        {
            "price": {"total": "850.00", "currency": "USD"},
            "itineraries": [
                {
                    "duration": "PT11H30M",
                    "segments": [
                        {
                            "carrierCode": "NH",
                            "number": "107",
                            "departure": {"at": "2026-06-15T10:00:00", "iataCode": "SEA"},
                            "arrival": {"at": "2026-06-16T14:30:00", "iataCode": "NRT"},
                        }
                    ],
                }
            ],
        }
    ]
}


class TestFlightsMocked:
    def setup_method(self):
        _token_cache.clear()

    @respx.mock
    async def test_returns_flight_results(self, monkeypatch):
        monkeypatch.setenv("AMADEUS_API_KEY", "test-key")
        monkeypatch.setenv("AMADEUS_API_SECRET", "test-secret")
        monkeypatch.setenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")

        respx.post("https://test.api.amadeus.com/v1/security/oauth2/token").mock(
            return_value=Response(200, json=_MOCK_TOKEN_RESPONSE)
        )
        respx.get("https://test.api.amadeus.com/v2/shopping/flight-offers").mock(
            return_value=Response(200, json=_MOCK_FLIGHTS_RESPONSE)
        )

        result = await search_flights.ainvoke({
            "origin": "SEA",
            "destination": "NRT",
            "departure_date": "2026-06-15",
            "adults": 1,
        })

        assert "SEA" in result
        assert "NRT" in result
        assert "850" in result
        assert "NH" in result

    @respx.mock
    async def test_no_flights_found(self, monkeypatch):
        monkeypatch.setenv("AMADEUS_API_KEY", "test-key")
        monkeypatch.setenv("AMADEUS_API_SECRET", "test-secret")
        monkeypatch.setenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")

        respx.post("https://test.api.amadeus.com/v1/security/oauth2/token").mock(
            return_value=Response(200, json=_MOCK_TOKEN_RESPONSE)
        )
        respx.get("https://test.api.amadeus.com/v2/shopping/flight-offers").mock(
            return_value=Response(200, json={"data": []})
        )

        result = await search_flights.ainvoke({
            "origin": "SEA",
            "destination": "NRT",
            "departure_date": "2026-06-15",
            "adults": 1,
        })

        assert "No flights found" in result

    @respx.mock
    async def test_non_stop_label(self, monkeypatch):
        monkeypatch.setenv("AMADEUS_API_KEY", "test-key")
        monkeypatch.setenv("AMADEUS_API_SECRET", "test-secret")
        monkeypatch.setenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")

        respx.post("https://test.api.amadeus.com/v1/security/oauth2/token").mock(
            return_value=Response(200, json=_MOCK_TOKEN_RESPONSE)
        )
        respx.get("https://test.api.amadeus.com/v2/shopping/flight-offers").mock(
            return_value=Response(200, json=_MOCK_FLIGHTS_RESPONSE)
        )

        result = await search_flights.ainvoke({
            "origin": "SEA",
            "destination": "NRT",
            "departure_date": "2026-06-15",
            "adults": 1,
        })

        assert "Non-stop" in result
