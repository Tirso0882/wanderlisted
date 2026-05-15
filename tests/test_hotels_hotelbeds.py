"""Unit tests for Hotelbeds hotel search tools — mocked HTTP responses."""

import json

import respx
from httpx import Response

from src.tools.hotels_hotelbeds import (
    search_hotels_hotelbeds,
    check_hotel_rate_hotelbeds,
    _hotelbeds_headers,
    _parse_star_rating,
    _format_cancellation,
    _format_taxes,
    _build_occupancies,
)


# ── Mock Payloads ─────────────────────────────────────────────────────────

_MOCK_AVAILABILITY_RESPONSE = {
    "hotels": {
        "hotels": [
            {
                "code": 12345,
                "name": "Ryokan Katsutaro",
                "categoryCode": "3EST",
                "categoryName": "3 STARS",
                "destinationName": "Tokyo",
                "zoneName": "Yanaka",
                "latitude": "35.7220",
                "longitude": "139.7660",
                "currency": "USD",
                "rooms": [
                    {
                        "code": "DBL.ST",
                        "name": "Double Standard",
                        "rates": [
                            {
                                "rateKey": "20260615|20260620|W|1|12345|DBL.ST|ID_B2B|RO|MRK1",
                                "net": "485.00",
                                "boardCode": "RO",
                                "boardName": "ROOM ONLY",
                                "rateType": "BOOKABLE",
                                "rooms": 1,
                                "adults": 2,
                                "children": 0,
                                "cancellationPolicies": [
                                    {
                                        "amount": "50.00",
                                        "from": "2026-06-13T23:59:00+09:00",
                                    },
                                ],
                                "dailyRates": [
                                    {"offset": 0, "dailyNet": "97.00"},
                                    {"offset": 1, "dailyNet": "97.00"},
                                    {"offset": 2, "dailyNet": "97.00"},
                                    {"offset": 3, "dailyNet": "97.00"},
                                    {"offset": 4, "dailyNet": "97.00"},
                                ],
                                "taxes": {
                                    "allIncluded": True,
                                    "taxes": [],
                                },
                                "promotions": [
                                    {"code": "073", "name": "Non-Refundable Rate"},
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "code": 67890,
                "name": "Hotel Granvia Kyoto",
                "categoryCode": "5EST",
                "categoryName": "5 STARS",
                "destinationName": "Kyoto",
                "zoneName": "Kyoto Station",
                "latitude": "34.9870",
                "longitude": "135.7585",
                "currency": "USD",
                "rooms": [
                    {
                        "code": "TWN.SU",
                        "name": "Twin Superior",
                        "rates": [
                            {
                                "rateKey": "20260615|20260620|W|1|67890|TWN.SU|ID_B2B|BB|MRK1",
                                "net": "1250.00",
                                "boardCode": "BB",
                                "boardName": "BED AND BREAKFAST",
                                "rateType": "RECHECK",
                                "rooms": 1,
                                "adults": 2,
                                "children": 0,
                                "cancellationPolicies": [
                                    {
                                        "amount": "0.00",
                                        "from": "2026-06-10T23:59:00+09:00",
                                    },
                                    {
                                        "amount": "625.00",
                                        "from": "2026-06-13T23:59:00+09:00",
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
        ],
        "total": 2,
    }
}

_MOCK_EMPTY_RESPONSE = {"hotels": {"hotels": [], "total": 0}}

_MOCK_CHECKRATE_RESPONSE = {
    "hotel": {
        "checkIn": "2026-06-15",
        "checkOut": "2026-06-20",
        "code": 12345,
        "name": "Ryokan Katsutaro",
        "totalNet": "490.00",
        "currency": "USD",
        "modificationPolicies": {
            "cancellation": True,
            "modification": True,
        },
        "rooms": [
            {
                "code": "DBL.ST",
                "name": "Double Standard",
                "rates": [
                    {
                        "rateKey": "20260615|20260620|W|1|12345|DBL.ST|ID_B2B|RO|MRK1",
                        "net": "490.00",
                        "boardCode": "RO",
                        "boardName": "ROOM ONLY",
                        "rateType": "BOOKABLE",
                        "cancellationPolicies": [
                            {"amount": "50.00", "from": "2026-06-13T23:59:00+09:00"},
                        ],
                        "rateBreakDown": {
                            "rateDiscounts": [
                                {
                                    "code": "EBD",
                                    "name": "Early Booking",
                                    "amount": "-25.00",
                                },
                            ],
                            "rateSupplements": [
                                {
                                    "code": "SNG",
                                    "name": "Single Supplement",
                                    "amount": "30.00",
                                },
                            ],
                        },
                        "rateComments": "Check-in from 15:00. Check-out before 11:00.",
                    }
                ],
            }
        ],
        "upselling": {
            "rooms": [
                {
                    "rates": [
                        {
                            "rateKey": "20260615|20260620|W|1|12345|DBL.DX|ID_B2B|BB|MRK1",
                            "net": "620.00",
                            "boardCode": "BB",
                            "boardName": "BED AND BREAKFAST",
                        }
                    ]
                }
            ],
        },
    }
}


# ── Helper Tests ──────────────────────────────────────────────────────────


class TestHelpers:
    def test_parse_star_rating_3est(self):
        assert "★★★" in _parse_star_rating("3EST")
        assert "3 stars" in _parse_star_rating("3EST")

    def test_parse_star_rating_5est(self):
        assert "★★★★★" in _parse_star_rating("5EST")

    def test_parse_star_rating_unknown(self):
        assert _parse_star_rating("LUXURY") == "LUXURY"

    def test_parse_star_rating_empty(self):
        assert _parse_star_rating("") == "N/A"

    def test_format_cancellation_with_policies(self):
        policies = [
            {"amount": "0.00", "from": "2026-06-10T23:59:00+09:00"},
            {"amount": "625.00", "from": "2026-06-13T23:59:00+09:00"},
        ]
        result = _format_cancellation(policies)
        assert "0.00" in result
        assert "2026-06-10" in result
        assert "625.00" in result

    def test_format_cancellation_empty(self):
        assert "No cancellation" in _format_cancellation([])

    def test_format_taxes_all_included(self):
        assert "included" in _format_taxes({"allIncluded": True, "taxes": []}).lower()

    def test_format_taxes_with_items(self):
        taxes = {
            "allIncluded": False,
            "taxes": [
                {
                    "included": False,
                    "amount": "10.00",
                    "currency": "EUR",
                    "type": "TAX",
                },
            ],
        }
        result = _format_taxes(taxes)
        assert "10.00" in result
        assert "EUR" in result

    def test_format_taxes_none(self):
        assert _format_taxes(None) == ""

    def test_build_occupancies_adults_only(self):
        result = _build_occupancies(1, 2, 0, None)
        assert result == [{"rooms": 1, "adults": 2, "children": 0}]

    def test_build_occupancies_with_children(self):
        result = _build_occupancies(1, 2, 2, [4, 8])
        occ = result[0]
        assert occ["children"] == 2
        assert occ["paxes"] == [{"type": "CH", "age": 4}, {"type": "CH", "age": 8}]


# ── Availability Tests ────────────────────────────────────────────────────


class TestSearchHotelsHotelbeds:
    @respx.mock
    async def test_returns_hotel_results(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/hotels").mock(
            return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE)
        )

        result = await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
                "adults": 2,
            }
        )

        assert "Hotelbeds" in result
        assert "Ryokan Katsutaro" in result
        assert "485" in result
        assert "ROOM ONLY" in result
        assert "Hotel Granvia Kyoto" in result
        assert "1250" in result

    @respx.mock
    async def test_returns_cancellation_info(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/hotels").mock(
            return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE)
        )

        result = await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
                "adults": 2,
            }
        )

        assert "Cancellation" in result
        assert "50.00" in result

    @respx.mock
    async def test_returns_daily_rates(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/hotels").mock(
            return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE)
        )

        result = await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
                "adults": 2,
            }
        )

        assert "Per night" in result
        assert "97.00" in result

    @respx.mock
    async def test_returns_location_data(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/hotels").mock(
            return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE)
        )

        result = await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
                "adults": 2,
            }
        )

        assert "Yanaka" in result
        assert "35.7220" in result

    @respx.mock
    async def test_flags_recheck_rates(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/hotels").mock(
            return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE)
        )

        result = await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
                "adults": 2,
            }
        )

        assert "RECHECK" in result
        assert "check_hotel_rate_hotelbeds" in result

    @respx.mock
    async def test_returns_promotions(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/hotels").mock(
            return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE)
        )

        result = await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
                "adults": 2,
            }
        )

        assert "Non-Refundable Rate" in result

    @respx.mock
    async def test_no_hotels_found(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/hotels").mock(
            return_value=Response(200, json=_MOCK_EMPTY_RESPONSE)
        )

        result = await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "XYZ",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
            }
        )

        assert "No hotel offers found on Hotelbeds" in result

    @respx.mock
    async def test_http_error_returns_message(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/hotels").mock(
            return_value=Response(403, text="Quota exceeded")
        )

        result = await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
            }
        )

        assert "error" in result.lower()
        assert "403" in result

    @respx.mock
    async def test_sends_correct_request_body(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        route_mock = respx.post(
            "https://api.test.hotelbeds.com/hotel-api/1.0/hotels"
        ).mock(return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE))

        await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "PAR",
                "check_in_date": "2026-09-01",
                "check_out_date": "2026-09-05",
                "adults": 2,
            }
        )

        body = json.loads(route_mock.calls[0].request.content)
        assert body["stay"]["checkIn"] == "2026-09-01"
        assert body["stay"]["checkOut"] == "2026-09-05"
        assert body["occupancies"][0]["adults"] == 2
        assert body["destination"]["code"] == "PAR"
        assert body["dailyRate"] is True

    @respx.mock
    async def test_sends_children_paxes(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        route_mock = respx.post(
            "https://api.test.hotelbeds.com/hotel-api/1.0/hotels"
        ).mock(return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE))

        await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "PAR",
                "check_in_date": "2026-09-01",
                "check_out_date": "2026-09-05",
                "adults": 2,
                "children": 2,
                "children_ages": "4,8",
            }
        )

        body = json.loads(route_mock.calls[0].request.content)
        occ = body["occupancies"][0]
        assert occ["children"] == 2
        assert occ["paxes"] == [{"type": "CH", "age": 4}, {"type": "CH", "age": 8}]

    @respx.mock
    async def test_sends_filters(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        route_mock = respx.post(
            "https://api.test.hotelbeds.com/hotel-api/1.0/hotels"
        ).mock(return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE))

        await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
                "adults": 2,
                "min_category": 3,
                "max_rate": 500.0,
                "board_codes": "BB,HB",
            }
        )

        body = json.loads(route_mock.calls[0].request.content)
        assert body["filter"]["minCategory"] == 3
        assert body["filter"]["maxRate"] == 500.0
        assert body["boards"] == {"board": ["BB", "HB"], "included": True}

    @respx.mock
    async def test_auth_headers_present(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        route_mock = respx.post(
            "https://api.test.hotelbeds.com/hotel-api/1.0/hotels"
        ).mock(return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE))

        await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
            }
        )

        headers = route_mock.calls[0].request.headers
        assert "api-key" in headers
        assert "x-signature" in headers

    async def test_missing_credentials_returns_error(self, monkeypatch):
        monkeypatch.delenv("HOTELBEDS_API_KEY", raising=False)
        monkeypatch.delenv("HOTELBEDS_API_SECRET", raising=False)

        result = await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
            }
        )

        assert "HOTELBEDS_API_KEY" in result

    @respx.mock
    async def test_star_rating_display(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/hotels").mock(
            return_value=Response(200, json=_MOCK_AVAILABILITY_RESPONSE)
        )

        result = await search_hotels_hotelbeds.ainvoke(
            {
                "city_code": "TYO",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-20",
            }
        )

        assert "★★★" in result  # 3EST → 3 stars
        assert "★★★★★" in result  # 5EST → 5 stars


# ── CheckRate Tests ───────────────────────────────────────────────────────


class TestCheckHotelRateHotelbeds:
    @respx.mock
    async def test_returns_checkrate_results(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/checkrates").mock(
            return_value=Response(200, json=_MOCK_CHECKRATE_RESPONSE)
        )

        result = await check_hotel_rate_hotelbeds.ainvoke(
            {
                "rate_keys": "20260615|20260620|W|1|12345|DBL.ST|ID_B2B|RO|MRK1",
            }
        )

        assert "Ryokan Katsutaro" in result
        assert "490.00" in result
        assert "ROOM ONLY" in result

    @respx.mock
    async def test_returns_rate_breakdown(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/checkrates").mock(
            return_value=Response(200, json=_MOCK_CHECKRATE_RESPONSE)
        )

        result = await check_hotel_rate_hotelbeds.ainvoke(
            {
                "rate_keys": "20260615|20260620|W|1|12345|DBL.ST|ID_B2B|RO|MRK1",
            }
        )

        assert "Early Booking" in result
        assert "25.00" in result
        assert "Single Supplement" in result
        assert "30.00" in result

    @respx.mock
    async def test_returns_modification_policies(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/checkrates").mock(
            return_value=Response(200, json=_MOCK_CHECKRATE_RESPONSE)
        )

        result = await check_hotel_rate_hotelbeds.ainvoke(
            {
                "rate_keys": "20260615|20260620|W|1|12345|DBL.ST|ID_B2B|RO|MRK1",
            }
        )

        assert "Modifications: Yes" in result
        assert "Cancellation: Yes" in result

    @respx.mock
    async def test_returns_upselling(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/checkrates").mock(
            return_value=Response(200, json=_MOCK_CHECKRATE_RESPONSE)
        )

        result = await check_hotel_rate_hotelbeds.ainvoke(
            {
                "rate_keys": "20260615|20260620|W|1|12345|DBL.ST|ID_B2B|RO|MRK1",
                "include_upselling": True,
            }
        )

        assert "Upselling" in result
        assert "620.00" in result
        assert "BED AND BREAKFAST" in result

    @respx.mock
    async def test_returns_rate_comments(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/checkrates").mock(
            return_value=Response(200, json=_MOCK_CHECKRATE_RESPONSE)
        )

        result = await check_hotel_rate_hotelbeds.ainvoke(
            {
                "rate_keys": "20260615|20260620|W|1|12345|DBL.ST|ID_B2B|RO|MRK1",
            }
        )

        assert "Check-in from 15:00" in result

    @respx.mock
    async def test_checkrate_http_error(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/checkrates").mock(
            return_value=Response(410, text="Rate expired")
        )

        result = await check_hotel_rate_hotelbeds.ainvoke(
            {
                "rate_keys": "20260615|20260620|W|1|12345|DBL.ST|ID_B2B|RO|MRK1",
            }
        )

        assert "error" in result.lower()
        assert "410" in result

    @respx.mock
    async def test_checkrate_no_hotel_data(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        respx.post("https://api.test.hotelbeds.com/hotel-api/1.0/checkrates").mock(
            return_value=Response(200, json={})
        )

        result = await check_hotel_rate_hotelbeds.ainvoke(
            {
                "rate_keys": "20260615|20260620|W|1|12345|DBL.ST|ID_B2B|RO|MRK1",
            }
        )

        assert "expired" in result.lower()

    async def test_checkrate_empty_rate_keys(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")

        result = await check_hotel_rate_hotelbeds.ainvoke(
            {
                "rate_keys": "",
            }
        )

        assert "No rate keys" in result

    @respx.mock
    async def test_checkrate_sends_correct_body(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "test-key")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "test-secret")
        monkeypatch.setenv("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com")

        route_mock = respx.post(
            "https://api.test.hotelbeds.com/hotel-api/1.0/checkrates"
        ).mock(return_value=Response(200, json=_MOCK_CHECKRATE_RESPONSE))

        await check_hotel_rate_hotelbeds.ainvoke(
            {
                "rate_keys": "key1|||key2",
                "include_upselling": True,
            }
        )

        body = json.loads(route_mock.calls[0].request.content)
        assert len(body["rooms"]) == 2
        assert body["rooms"][0]["rateKey"] == "key1"
        assert body["rooms"][1]["rateKey"] == "key2"
        assert body["upselling"] is True


# ── Header Tests ──────────────────────────────────────────────────────────


class TestHotelbedHeaders:
    def test_builds_headers_with_signature(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_API_KEY", "mykey")
        monkeypatch.setenv("HOTELBEDS_API_SECRET", "mysecret")

        headers = _hotelbeds_headers()
        assert headers["Api-key"] == "mykey"
        assert len(headers["X-Signature"]) == 64  # SHA256 hex is 64 chars
        assert headers["Accept"] == "application/json"
        assert headers["Accept-Encoding"] == "gzip"

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("HOTELBEDS_API_KEY", raising=False)
        monkeypatch.delenv("HOTELBEDS_API_SECRET", raising=False)

        import pytest

        with pytest.raises(RuntimeError, match="HOTELBEDS_API_KEY"):
            _hotelbeds_headers()
