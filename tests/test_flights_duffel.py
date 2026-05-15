"""Unit tests for Duffel flight tools — mocked API responses."""

import respx
from httpx import Response

from src.tools.flights_duffel import (
    confirm_flight_price,
    get_cheapest_flight,
    search_cheapest_flight_in_month,
    search_flights,
    search_nearby_airports,
)


# ── Mock Responses ───────────────────────────────────────────────────────

_MOCK_OFFER_REQUEST_RESPONSE = {
    "data": {
        "id": "orq_00009hthhsUZ8W4LxQghdf",
        "slices": [
            {
                "origin": {"iata_code": "JFK", "type": "airport"},
                "destination": {"iata_code": "LHR", "type": "airport"},
            }
        ],
        "passengers": [{"id": "pas_0000AUde3KY1SptM6ABSfU", "type": "adult"}],
        "offers": [
            {
                "id": "off_00009htyDGjIfajdNBZRlw",
                "total_amount": "450.00",
                "total_currency": "GBP",
                "owner": {"iata_code": "BA", "name": "British Airways"},
                "slices": [
                    {
                        "origin": {"iata_code": "JFK", "name": "John F. Kennedy International Airport"},
                        "destination": {"iata_code": "LHR", "name": "Heathrow Airport"},
                        "duration": "PT7H30M",
                        "segments": [
                            {
                                "origin": {"iata_code": "JFK"},
                                "destination": {"iata_code": "LHR"},
                                "departing_at": "2026-08-15T19:30:00",
                                "arriving_at": "2026-08-16T07:00:00",
                                "operating_carrier": {"iata_code": "BA", "name": "British Airways"},
                                "operating_carrier_flight_number": "178",
                                "duration": "PT7H30M",
                                "passengers": [
                                    {
                                        "cabin_class": "economy",
                                        "cabin_class_marketing_name": "Economy Basic",
                                        "baggages": [
                                            {"type": "carry_on", "quantity": 1},
                                            {"type": "checked", "quantity": 0},
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "conditions": {
                    "change_before_departure": {
                        "allowed": True,
                        "penalty_amount": "50.00",
                        "penalty_currency": "GBP",
                    },
                    "refund_before_departure": {
                        "allowed": False,
                        "penalty_amount": None,
                        "penalty_currency": None,
                    },
                },
                "payment_requirements": {
                    "requires_instant_payment": True,
                    "price_guarantee_expires_at": None,
                    "payment_required_by": None,
                },
            },
            {
                "id": "off_00009htyDGjIfajdNBZRlx",
                "total_amount": "720.00",
                "total_currency": "GBP",
                "owner": {"iata_code": "BA", "name": "British Airways"},
                "slices": [
                    {
                        "origin": {"iata_code": "JFK", "name": "John F. Kennedy International Airport"},
                        "destination": {"iata_code": "LHR", "name": "Heathrow Airport"},
                        "duration": "PT7H30M",
                        "segments": [
                            {
                                "origin": {"iata_code": "JFK"},
                                "destination": {"iata_code": "LHR"},
                                "departing_at": "2026-08-15T19:30:00",
                                "arriving_at": "2026-08-16T07:00:00",
                                "operating_carrier": {"iata_code": "BA", "name": "British Airways"},
                                "operating_carrier_flight_number": "178",
                                "duration": "PT7H30M",
                                "passengers": [
                                    {
                                        "cabin_class": "economy",
                                        "cabin_class_marketing_name": "Economy Comfort",
                                        "baggages": [
                                            {"type": "carry_on", "quantity": 1},
                                            {"type": "checked", "quantity": 1},
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "conditions": {
                    "change_before_departure": {
                        "allowed": True,
                        "penalty_amount": "0.00",
                        "penalty_currency": "GBP",
                    },
                    "refund_before_departure": {
                        "allowed": True,
                        "penalty_amount": "100.00",
                        "penalty_currency": "GBP",
                    },
                },
                "payment_requirements": {
                    "requires_instant_payment": False,
                    "price_guarantee_expires_at": "2026-08-10T23:59:59Z",
                    "payment_required_by": "2026-08-14T23:59:59Z",
                },
            },
        ],
    }
}

_MOCK_SINGLE_OFFER_RESPONSE = {
    "data": {
        "id": "off_00009htyDGjIfajdNBZRlw",
        "total_amount": "455.00",
        "total_currency": "GBP",
        "owner": {"iata_code": "BA", "name": "British Airways"},
        "slices": [
            {
                "origin": {"iata_code": "JFK"},
                "destination": {"iata_code": "LHR"},
                "duration": "PT7H30M",
                "segments": [
                    {
                        "origin": {"iata_code": "JFK"},
                        "destination": {"iata_code": "LHR"},
                        "departing_at": "2026-08-15T19:30:00",
                        "arriving_at": "2026-08-16T07:00:00",
                        "operating_carrier": {"iata_code": "BA", "name": "British Airways"},
                        "operating_carrier_flight_number": "178",
                        "duration": "PT7H30M",
                        "passengers": [
                            {
                                "cabin_class": "economy",
                                "cabin_class_marketing_name": "Economy Basic",
                                "baggages": [
                                    {"type": "carry_on", "quantity": 1},
                                    {"type": "checked", "quantity": 0},
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "conditions": {
            "change_before_departure": {
                "allowed": True,
                "penalty_amount": "50.00",
                "penalty_currency": "GBP",
            },
            "refund_before_departure": {
                "allowed": False,
                "penalty_amount": None,
                "penalty_currency": None,
            },
        },
        "payment_requirements": {
            "requires_instant_payment": True,
            "price_guarantee_expires_at": None,
            "payment_required_by": None,
        },
    }
}

_MOCK_PLACES_RESPONSE = {
    "data": [
        {
            "type": "airport",
            "time_zone": "Europe/Lisbon",
            "name": "Faro Airport",
            "longitude": -7.967814,
            "latitude": 37.015998,
            "id": "arp_fao_pt",
            "icao_code": "LPFR",
            "iata_country_code": "PT",
            "iata_code": "FAO",
            "iata_city_code": "FAO",
            "city_name": "Faro",
        },
        {
            "type": "airport",
            "time_zone": "Europe/Lisbon",
            "name": "Portimão Airport",
            "longitude": -8.582632,
            "latitude": 37.148769,
            "id": "arp_prm_pt",
            "icao_code": "LPPM",
            "iata_country_code": "PT",
            "iata_code": "PRM",
            "iata_city_code": "PRM",
            "city_name": "Portimão",
        },
    ]
}


# ── Tests ────────────────────────────────────────────────────────────────


@respx.mock
async def test_search_flights_basic(monkeypatch):
    """Test basic flight search returns formatted results."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    result = await search_flights.ainvoke(
        {"origin": "JFK", "destination": "LHR", "departure_date": "2026-08-15"}
    )

    assert "JFK" in result
    assert "LHR" in result
    assert "BA178" in result
    assert "British Airways" in result
    assert "450.00" in result
    assert "Non-stop" in result
    assert "Economy Basic" in result
    assert "1 carry on" in result
    assert "Change:" in result


@respx.mock
async def test_search_flights_no_results(monkeypatch):
    """Test empty results message."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    empty_response = {"data": {"id": "orq_test", "offers": [], "slices": [], "passengers": []}}
    respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=empty_response)
    )

    result = await search_flights.ainvoke(
        {"origin": "XXX", "destination": "YYY", "departure_date": "2026-08-15"}
    )

    assert "No flights found" in result


@respx.mock
async def test_search_flights_api_error(monkeypatch):
    """Test graceful handling of API errors."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    error_response = {
        "meta": {"status": 422, "request_id": "req_test"},
        "errors": [{"type": "validation_error", "message": "Invalid origin", "title": "Bad Request"}],
    }
    respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(422, json=error_response)
    )

    result = await search_flights.ainvoke(
        {"origin": "INVALID", "destination": "LHR", "departure_date": "2026-08-15"}
    )

    assert "error" in result.lower() or "Invalid origin" in result


@respx.mock
async def test_search_flights_with_cabin_class(monkeypatch):
    """Test that cabin_class is passed to the API."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    route = respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    await search_flights.ainvoke(
        {
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": "2026-08-15",
            "travel_class": "BUSINESS",
        }
    )

    request_body = route.calls[0].request.content
    import json

    body = json.loads(request_body)
    assert body["data"]["cabin_class"] == "business"


@respx.mock
async def test_search_flights_non_stop(monkeypatch):
    """Test that non_stop=True sets max_connections=0."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    route = respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    await search_flights.ainvoke(
        {
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": "2026-08-15",
            "non_stop": True,
        }
    )

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["data"]["max_connections"] == 0


@respx.mock
async def test_search_flights_round_trip(monkeypatch):
    """Test round trip includes two slices in request."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    route = respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    await search_flights.ainvoke(
        {
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": "2026-08-15",
            "return_date": "2026-08-22",
        }
    )

    import json

    body = json.loads(route.calls[0].request.content)
    assert len(body["data"]["slices"]) == 2
    assert body["data"]["slices"][1]["origin"] == "LHR"
    assert body["data"]["slices"][1]["destination"] == "JFK"
    assert body["data"]["slices"][1]["departure_date"] == "2026-08-22"


@respx.mock
async def test_search_flights_passengers(monkeypatch):
    """Test passenger types are built correctly."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    route = respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    await search_flights.ainvoke(
        {
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": "2026-08-15",
            "adults": 2,
            "children": 1,
            "infants": 1,
        }
    )

    import json

    body = json.loads(route.calls[0].request.content)
    passengers = body["data"]["passengers"]
    assert len(passengers) == 4
    assert sum(1 for p in passengers if p.get("type") == "adult") == 2
    assert sum(1 for p in passengers if p.get("age") == 8) == 1
    assert sum(1 for p in passengers if p.get("age") == 0) == 1


@respx.mock
async def test_confirm_flight_price(monkeypatch):
    """Test price confirmation re-fetches offer and reports price change."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )
    respx.get("https://api.duffel.com/air/offers/off_00009htyDGjIfajdNBZRlw").mock(
        return_value=Response(200, json=_MOCK_SINGLE_OFFER_RESPONSE)
    )

    result = await confirm_flight_price.ainvoke(
        {
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": "2026-08-15",
            "offer_index": 1,
        }
    )

    assert "✅ Price confirmed" in result
    assert "455.00" in result
    # Price changed from 450 to 455
    assert "Price changed" in result


@respx.mock
async def test_confirm_flight_price_hold_offer(monkeypatch):
    """Test that hold-eligible offers show payment info."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    # Return the second offer (hold-eligible) when fetched
    hold_offer_response = {
        "data": {
            **_MOCK_OFFER_REQUEST_RESPONSE["data"]["offers"][1],
        }
    }
    respx.get("https://api.duffel.com/air/offers/off_00009htyDGjIfajdNBZRlx").mock(
        return_value=Response(200, json=hold_offer_response)
    )

    result = await confirm_flight_price.ainvoke(
        {
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": "2026-08-15",
            "offer_index": 2,
        }
    )

    assert "held without immediate payment" in result


@respx.mock
async def test_confirm_flight_price_invalid_index(monkeypatch):
    """Test invalid offer index returns error message."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    result = await confirm_flight_price.ainvoke(
        {
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": "2026-08-15",
            "offer_index": 99,
        }
    )

    assert "Invalid offer_index" in result


@respx.mock
async def test_get_cheapest_flight(monkeypatch):
    """Test cheapest flight returns the lowest-priced offer."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    result = await get_cheapest_flight.ainvoke(
        {"origin": "JFK", "destination": "LHR", "departure_date": "2026-08-15"}
    )

    assert "Cheapest flight" in result
    assert "450.00" in result  # Cheapest of 450 and 720


@respx.mock
async def test_search_cheapest_flight_in_month(monkeypatch):
    """Test multi-date monthly search aggregates results."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    result = await search_cheapest_flight_in_month.ainvoke(
        {"origin": "JFK", "destination": "LHR", "year": 2027, "month": 3}
    )

    assert "Cheapest flights" in result
    assert "450.00" in result


@respx.mock
async def test_search_cheapest_flight_in_month_past(monkeypatch):
    """Test past month returns no-future-dates message."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    result = await search_cheapest_flight_in_month.ainvoke(
        {"origin": "JFK", "destination": "LHR", "year": 2020, "month": 1}
    )

    assert "No future dates" in result


@respx.mock
async def test_search_nearby_airports(monkeypatch):
    """Test airport discovery by location."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    respx.get(url__startswith="https://api.duffel.com/places/suggestions").mock(
        return_value=Response(200, json=_MOCK_PLACES_RESPONSE)
    )

    result = await search_nearby_airports.ainvoke(
        {"latitude": 37.13, "longitude": -8.67, "radius_km": 100}
    )

    assert "FAO" in result
    assert "Faro Airport" in result
    assert "PRM" in result
    assert "Portimão" in result


@respx.mock
async def test_search_nearby_airports_no_results(monkeypatch):
    """Test empty airport results."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    respx.get(url__startswith="https://api.duffel.com/places/suggestions").mock(
        return_value=Response(200, json={"data": []})
    )

    result = await search_nearby_airports.ainvoke(
        {"latitude": 0.0, "longitude": 0.0, "radius_km": 50}
    )

    assert "No airports found" in result


@respx.mock
async def test_search_flights_conditions_formatting(monkeypatch):
    """Test that conditions are displayed in output."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    result = await search_flights.ainvoke(
        {"origin": "JFK", "destination": "LHR", "departure_date": "2026-08-15"}
    )

    # First offer: change allowed with fee, refund not allowed
    assert "GBP 50.00 fee" in result
    assert "Refund: Not allowed" in result


@respx.mock
async def test_search_flights_sorted_by_price(monkeypatch):
    """Test that results are sorted cheapest first."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    respx.post("https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    result = await search_flights.ainvoke(
        {"origin": "JFK", "destination": "LHR", "departure_date": "2026-08-15"}
    )

    # 450 should appear before 720
    pos_450 = result.index("450.00")
    pos_720 = result.index("720.00")
    assert pos_450 < pos_720


@respx.mock
async def test_search_flights_supplier_timeout_in_url(monkeypatch):
    """Test that supplier_timeout is included as query parameter."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")
    monkeypatch.setenv("DUFFEL_SUPPLIER_TIMEOUT", "20000")

    route = respx.post(url__startswith="https://api.duffel.com/air/offer_requests").mock(
        return_value=Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE)
    )

    await search_flights.ainvoke(
        {"origin": "JFK", "destination": "LHR", "departure_date": "2026-08-15"}
    )

    request_url = str(route.calls[0].request.url)
    assert "supplier_timeout=" in request_url


@respx.mock
async def test_search_flights_retry_on_429(monkeypatch):
    """Test that 429 triggers retry (eventually succeeds)."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    route = respx.post("https://api.duffel.com/air/offer_requests")
    route.side_effect = [
        Response(429, json={"errors": [{"message": "Rate limited"}]}),
        Response(200, json=_MOCK_OFFER_REQUEST_RESPONSE),
    ]

    result = await search_flights.ainvoke(
        {"origin": "JFK", "destination": "LHR", "departure_date": "2026-08-15"}
    )

    assert "BA178" in result
    assert len(route.calls) == 2


@respx.mock
async def test_search_nearby_airports_radius_capped(monkeypatch):
    """Test radius is capped at 200km."""
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_mock123")

    route = respx.get(url__startswith="https://api.duffel.com/places/suggestions").mock(
        return_value=Response(200, json=_MOCK_PLACES_RESPONSE)
    )

    await search_nearby_airports.ainvoke(
        {"latitude": 37.13, "longitude": -8.67, "radius_km": 500}
    )

    request_url = str(route.calls[0].request.url)
    # 200km * 1000 = 200000 meters (capped from 500km)
    assert "rad=200000" in request_url
