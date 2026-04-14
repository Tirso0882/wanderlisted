"""Unit tests for hotel search tool — mocked Amadeus API responses."""

import respx
from httpx import Response

from src.tools.flights import _token_cache
from src.tools.hotels import search_hotels


_MOCK_TOKEN_RESPONSE = {
    "access_token": "mock-token-12345",
    "token_type": "Bearer",
    "expires_in": 1799,
}

_MOCK_HOTELS_BY_CITY = {
    "data": [
        {"hotelId": "TYABC123"},
        {"hotelId": "TYDEF456"},
    ]
}

_MOCK_HOTEL_OFFERS = {
    "data": [
        {
            "hotel": {"name": "Hotel Sunroute Plaza Tokyo", "rating": "4"},
            "offers": [
                {
                    "price": {"total": "620.00", "currency": "USD"},
                    "checkInDate": "2026-06-15",
                    "checkOutDate": "2026-06-20",
                    "room": {
                        "typeEstimated": {
                            "bedType": "DOUBLE",
                            "beds": 1,
                            "category": "STANDARD",
                        }
                    },
                }
            ],
        }
    ]
}


class TestHotelsMocked:
    def setup_method(self):
        _token_cache.clear()

    @respx.mock
    async def test_returns_hotel_results(self, monkeypatch):
        monkeypatch.setenv("AMADEUS_API_KEY", "test-key")
        monkeypatch.setenv("AMADEUS_API_SECRET", "test-secret")
        monkeypatch.setenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")

        respx.post("https://test.api.amadeus.com/v1/security/oauth2/token").mock(
            return_value=Response(200, json=_MOCK_TOKEN_RESPONSE)
        )
        respx.get(url__regex=r"hotels/by-city").mock(
            return_value=Response(200, json=_MOCK_HOTELS_BY_CITY)
        )
        respx.get(url__regex=r"hotel-offers").mock(
            return_value=Response(200, json=_MOCK_HOTEL_OFFERS)
        )

        result = await search_hotels.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
                "adults": 2,
            }
        )

        assert "Hotel Sunroute" in result
        assert "620" in result
        assert "TYO" in result

    @respx.mock
    async def test_no_hotels_found(self, monkeypatch):
        monkeypatch.setenv("AMADEUS_API_KEY", "test-key")
        monkeypatch.setenv("AMADEUS_API_SECRET", "test-secret")
        monkeypatch.setenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")

        respx.post("https://test.api.amadeus.com/v1/security/oauth2/token").mock(
            return_value=Response(200, json=_MOCK_TOKEN_RESPONSE)
        )
        respx.get(url__regex=r"hotels/by-city").mock(
            return_value=Response(200, json={"data": []})
        )

        result = await search_hotels.ainvoke(
            {
                "city_code": "XYZ",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
                "adults": 1,
            }
        )

        assert "No hotel offers found" in result
