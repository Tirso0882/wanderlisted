"""Unit tests for Google Maps Platform tools — mocked HTTP responses."""

import json

import httpx
import respx
from httpx import Response

from src.tools.google_maps import (
    search_places_nearby,
    search_places_text,
    get_directions,
    get_distance_matrix,
    compute_route,
    optimize_day_route,
    get_timezone,
    _format_place,
    _looks_like_latlng,
    _geocode,
    places_photo_url,
    directions_embed_url,
    lookup_place_photo,
)

# ── Mock payloads ────────────────────────────────────────────────────────

_MOCK_PLACE = {
    "displayName": {"text": "Sala de Baile Alicante"},
    "formattedAddress": "Calle Pintor Murillo 39, Alicante",
    "rating": 4.8,
    "userRatingCount": 120,
    "priceLevel": "PRICE_LEVEL_MODERATE",
    "types": ["gym", "point_of_interest"],
    "businessStatus": "OPERATIONAL",
    "location": {"latitude": 38.3452, "longitude": -0.4810},
}

_MOCK_PLACES_RESPONSE = {"places": [_MOCK_PLACE]}

_MOCK_GEOCODE_RESPONSE = {
    "status": "OK",
    "results": [{"geometry": {"location": {"lat": 38.3452, "lng": -0.4810}}}],
}

_MOCK_DIRECTIONS_RESPONSE = {
    "status": "OK",
    "routes": [
        {
            "legs": [
                {
                    "start_address": "Alicante Station",
                    "end_address": "Playa Postiguet",
                    "distance": {"text": "2.1 km"},
                    "duration": {"text": "8 mins"},
                    "steps": [
                        {
                            "html_instructions": "Head <b>south</b>",
                            "distance": {"text": "0.5 km"},
                            "duration": {"text": "2 mins"},
                        },
                        {
                            "html_instructions": "Turn <b>left</b> onto Av Salamanca",
                            "distance": {"text": "1.6 km"},
                            "duration": {"text": "6 mins"},
                        },
                    ],
                }
            ]
        }
    ],
}

_MOCK_DISTANCE_MATRIX_RESPONSE = {
    "status": "OK",
    "origin_addresses": ["Alicante Station"],
    "destination_addresses": ["Playa Postiguet", "Castle of Santa Barbara"],
    "rows": [
        {
            "elements": [
                {
                    "status": "OK",
                    "distance": {"text": "2.1 km"},
                    "duration": {"text": "8 mins"},
                },
                {
                    "status": "OK",
                    "distance": {"text": "3.5 km"},
                    "duration": {"text": "12 mins"},
                },
            ]
        }
    ],
}

_MOCK_ROUTES_RESPONSE = {
    "routes": [
        {
            "distanceMeters": 15400,
            "duration": "2520s",
            "optimizedIntermediateWaypointIndex": [1, 0, 2],
            "legs": [
                {"distanceMeters": 3000, "duration": "600s"},
                {"distanceMeters": 5000, "duration": "900s"},
                {"distanceMeters": 4000, "duration": "720s"},
                {"distanceMeters": 3400, "duration": "300s"},
            ],
        }
    ],
}


# ── Helper tests ─────────────────────────────────────────────────────────


class TestHelpers:
    def test_looks_like_latlng_valid(self):
        assert _looks_like_latlng("38.3452,-0.4810") is True

    def test_looks_like_latlng_text(self):
        assert _looks_like_latlng("Alicante, Spain") is False

    def test_looks_like_latlng_single_number(self):
        assert _looks_like_latlng("38.3452") is False

    def test_format_place_basic(self):
        result = _format_place(_MOCK_PLACE)
        assert "Sala de Baile Alicante" in result
        assert "4.8/5" in result
        assert "$$" in result
        assert "Calle Pintor Murillo" in result

    def test_format_place_minimal(self):
        result = _format_place({"displayName": {"text": "Test Place"}})
        assert "Test Place" in result

    @respx.mock
    def test_geocode_success(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
            return_value=Response(200, json=_MOCK_GEOCODE_RESPONSE)
        )
        result = _geocode("Alicante, Spain", "test-key")
        assert result == "38.3452,-0.481"

    @respx.mock
    def test_geocode_no_results(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
            return_value=Response(200, json={"status": "ZERO_RESULTS", "results": []})
        )
        result = _geocode("Nonexistent Place", "test-key")
        assert result is None

    @respx.mock
    def test_geocode_http_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
            return_value=Response(500, text="Internal Server Error")
        )
        result = _geocode("Alicante", "test-key")
        assert result is None


# ── search_places_nearby ─────────────────────────────────────────────────


class TestSearchPlacesNearby:
    @respx.mock
    async def test_returns_results(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchNearby").mock(
            return_value=Response(200, json=_MOCK_PLACES_RESPONSE)
        )
        result = await search_places_nearby.ainvoke(
            {
                "location": "38.3452,-0.4810",
                "place_type": "gym",
            }
        )
        assert "Sala de Baile Alicante" in result
        assert "Found 1" in result

    @respx.mock
    async def test_no_results(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchNearby").mock(
            return_value=Response(200, json={"places": []})
        )
        result = await search_places_nearby.ainvoke(
            {
                "location": "38.3452,-0.4810",
                "place_type": "gym",
            }
        )
        assert "No gym found" in result

    @respx.mock
    async def test_geocodes_text_location(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
            return_value=Response(200, json=_MOCK_GEOCODE_RESPONSE)
        )
        respx.post("https://places.googleapis.com/v1/places:searchNearby").mock(
            return_value=Response(200, json=_MOCK_PLACES_RESPONSE)
        )
        result = await search_places_nearby.ainvoke(
            {
                "location": "Alicante, Spain",
                "place_type": "restaurant",
            }
        )
        assert "Sala de Baile" in result

    @respx.mock
    async def test_http_error_returns_message(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchNearby").mock(
            return_value=Response(403, text="Forbidden")
        )
        result = await search_places_nearby.ainvoke(
            {
                "location": "38.3452,-0.4810",
                "place_type": "gym",
            }
        )
        assert "error" in result.lower()
        assert "403" in result

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        import pytest

        with pytest.raises(RuntimeError, match="GOOGLE_MAPS_API_KEY"):
            search_places_nearby.invoke(
                {
                    "location": "38.3452,-0.4810",
                    "place_type": "gym",
                }
            )


# ── search_places_text ───────────────────────────────────────────────────


class TestSearchPlacesText:
    @respx.mock
    async def test_returns_results(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(200, json=_MOCK_PLACES_RESPONSE)
        )
        result = await search_places_text.ainvoke(
            {
                "query": "dance studio room rental Alicante",
            }
        )
        assert "Sala de Baile Alicante" in result
        assert "Found 1" in result

    @respx.mock
    async def test_no_results(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(200, json={"places": []})
        )
        result = await search_places_text.ainvoke(
            {
                "query": "nonexistent place type",
            }
        )
        assert "No places found" in result

    @respx.mock
    async def test_max_results_clamped(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        route = respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(200, json=_MOCK_PLACES_RESPONSE)
        )
        await search_places_text.ainvoke(
            {
                "query": "restaurants in Barcelona",
                "max_results": 50,
            }
        )
        body = json.loads(route.calls[0].request.content)
        assert body["maxResultCount"] == 20

    @respx.mock
    async def test_http_error_returns_message(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(500, text="Server Error")
        )
        result = await search_places_text.ainvoke({"query": "test"})
        assert "error" in result.lower()
        assert "500" in result


# ── get_directions ───────────────────────────────────────────────────────


class TestGetDirections:
    @respx.mock
    async def test_returns_route(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/directions/json").mock(
            return_value=Response(200, json=_MOCK_DIRECTIONS_RESPONSE)
        )
        result = await get_directions.ainvoke(
            {
                "origin": "Alicante Station",
                "destination": "Playa Postiguet",
            }
        )
        assert "Alicante Station" in result
        assert "Playa Postiguet" in result
        assert "2.1 km" in result
        assert "8 mins" in result

    @respx.mock
    async def test_api_status_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/directions/json").mock(
            return_value=Response(200, json={"status": "NOT_FOUND"})
        )
        result = await get_directions.ainvoke(
            {
                "origin": "Nowhere",
                "destination": "Nowhere Else",
            }
        )
        assert "NOT_FOUND" in result

    @respx.mock
    async def test_http_error_returns_message(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/directions/json").mock(
            return_value=Response(429, text="Rate limited")
        )
        result = await get_directions.ainvoke(
            {
                "origin": "A",
                "destination": "B",
            }
        )
        assert "error" in result.lower()
        assert "429" in result


# ── get_distance_matrix ──────────────────────────────────────────────────


class TestGetDistanceMatrix:
    @respx.mock
    async def test_returns_matrix(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/distancematrix/json").mock(
            return_value=Response(200, json=_MOCK_DISTANCE_MATRIX_RESPONSE)
        )
        result = await get_distance_matrix.ainvoke(
            {
                "origins": "Alicante Station",
                "destinations": "Playa Postiguet|Castle of Santa Barbara",
            }
        )
        assert "2.1 km" in result
        assert "3.5 km" in result
        assert "driving" in result.lower()

    @respx.mock
    async def test_api_status_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/distancematrix/json").mock(
            return_value=Response(200, json={"status": "INVALID_REQUEST"})
        )
        result = await get_distance_matrix.ainvoke(
            {
                "origins": "bad",
                "destinations": "bad",
            }
        )
        assert "INVALID_REQUEST" in result

    @respx.mock
    async def test_http_error_returns_message(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/distancematrix/json").mock(
            return_value=Response(403, text="Forbidden")
        )
        result = await get_distance_matrix.ainvoke(
            {
                "origins": "A",
                "destinations": "B",
            }
        )
        assert "error" in result.lower()


# ── compute_route ────────────────────────────────────────────────────────


class TestComputeRoute:
    @respx.mock
    async def test_returns_route(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").mock(
            return_value=Response(200, json=_MOCK_ROUTES_RESPONSE)
        )
        result = await compute_route.ainvoke(
            {
                "origin": "Alicante",
                "destination": "Malaga",
            }
        )
        assert "15.4 km" in result
        assert "DRIVE" in result

    @respx.mock
    async def test_with_waypoints(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        route_mock = respx.post(
            "https://routes.googleapis.com/directions/v2:computeRoutes"
        ).mock(return_value=Response(200, json=_MOCK_ROUTES_RESPONSE))
        result = await compute_route.ainvoke(
            {
                "origin": "Alicante",
                "destination": "Malaga",
                "waypoints": "Murcia, Granada, Almeria",
            }
        )
        body = json.loads(route_mock.calls[0].request.content)
        assert len(body["intermediates"]) == 3
        assert body["optimizeWaypointOrder"] is True
        assert "Optimised stop order" in result

    @respx.mock
    async def test_no_routes_found(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").mock(
            return_value=Response(200, json={"routes": []})
        )
        result = await compute_route.ainvoke(
            {
                "origin": "A",
                "destination": "B",
            }
        )
        assert "No route found" in result

    @respx.mock
    async def test_http_error_returns_message(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").mock(
            return_value=Response(400, text="Bad Request")
        )
        result = await compute_route.ainvoke(
            {
                "origin": "A",
                "destination": "B",
            }
        )
        assert "error" in result.lower()
        assert "400" in result


# ── optimize_day_route ───────────────────────────────────────────────────


class TestOptimizeDayRoute:
    @respx.mock
    async def test_returns_optimised_route(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").mock(
            return_value=Response(200, json=_MOCK_ROUTES_RESPONSE)
        )
        result = await optimize_day_route.ainvoke(
            {
                "stops": "Playa Postiguet, Castle of Santa Barbara, Mercado Central",
                "start_location": "Hotel Alicante",
            }
        )
        assert "Optimised day route" in result
        assert "3 stops" in result
        assert "15.4 km" in result
        assert "Hotel Alicante" in result

    @respx.mock
    async def test_defaults_end_to_start(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        two_stop_response = {
            "routes": [
                {
                    "distanceMeters": 8000,
                    "duration": "1500s",
                    "optimizedIntermediateWaypointIndex": [1, 0],
                    "legs": [
                        {"distanceMeters": 3000, "duration": "600s"},
                        {"distanceMeters": 2000, "duration": "400s"},
                        {"distanceMeters": 3000, "duration": "500s"},
                    ],
                }
            ],
        }
        route_mock = respx.post(
            "https://routes.googleapis.com/directions/v2:computeRoutes"
        ).mock(return_value=Response(200, json=two_stop_response))
        await optimize_day_route.ainvoke(
            {
                "stops": "A, B",
                "start_location": "Hotel",
            }
        )
        body = json.loads(route_mock.calls[0].request.content)
        assert body["origin"] == body["destination"]

    @respx.mock
    async def test_no_routes_found(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").mock(
            return_value=Response(200, json={"routes": []})
        )
        result = await optimize_day_route.ainvoke(
            {
                "stops": "A, B",
                "start_location": "Hotel",
            }
        )
        assert "Could not compute" in result

    @respx.mock
    async def test_http_error_returns_message(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").mock(
            return_value=Response(500, text="Server Error")
        )
        result = await optimize_day_route.ainvoke(
            {
                "stops": "A, B",
                "start_location": "Hotel",
            }
        )
        assert "error" in result.lower()


# ── places_photo_url ─────────────────────────────────────────────────────

_MOCK_TIMEZONE_RESPONSE = {
    "status": "OK",
    "timeZoneId": "Asia/Tokyo",
    "timeZoneName": "Japan Standard Time",
    "rawOffset": 32400,
    "dstOffset": 0,
}


class TestPlacesPhotoUrl:
    def test_builds_url(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        result = places_photo_url("places/ChIJ123/photos/AU_ZVE456")
        assert (
            "places.googleapis.com/v1/places/ChIJ123/photos/AU_ZVE456/media" in result
        )
        assert "maxHeightPx=400" in result
        assert "key=test-key" in result

    def test_custom_height(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        result = places_photo_url("places/X/photos/Y", max_height=200)
        assert "maxHeightPx=200" in result

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        import pytest

        with pytest.raises(RuntimeError, match="GOOGLE_MAPS_API_KEY"):
            places_photo_url("places/X/photos/Y")


# ── directions_embed_url ─────────────────────────────────────────────────


class TestDirectionsEmbedUrl:
    def test_basic_url(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        result = directions_embed_url("Tokyo Station", "Senso-ji Temple")
        assert "google.com/maps/embed/v1/directions" in result
        assert "origin=Tokyo+Station" in result
        assert "destination=Senso-ji+Temple" in result
        assert "mode=walking" in result

    def test_with_waypoints(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        result = directions_embed_url("A", "C", waypoints=["B1", "B2"], mode="driving")
        assert "waypoints=B1%7CB2" in result
        assert "mode=driving" in result

    def test_no_waypoints(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        result = directions_embed_url("A", "B")
        assert "waypoints" not in result


# ── lookup_place_photo ───────────────────────────────────────────────────


class TestLookupPlacePhoto:
    @respx.mock
    def test_returns_photo_url(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(
                200,
                json={
                    "places": [
                        {
                            "displayName": {"text": "Tokyo Tower"},
                            "photos": [{"name": "places/abc/photos/xyz"}],
                        }
                    ]
                },
            )
        )
        result = lookup_place_photo("Tokyo Tower", "Tokyo")
        assert result is not None
        assert "places.googleapis.com" in result

    @respx.mock
    def test_no_photos_returns_none(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(
                200,
                json={"places": [{"displayName": {"text": "Test"}, "photos": []}]},
            )
        )
        result = lookup_place_photo("No Photos Place")
        assert result is None

    @respx.mock
    def test_no_places_returns_none(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(200, json={"places": []})
        )
        result = lookup_place_photo("Nonexistent")
        assert result is None

    @respx.mock
    def test_http_error_returns_none(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(500, text="Error")
        )
        result = lookup_place_photo("Some Place")
        assert result is None


# ── get_timezone ─────────────────────────────────────────────────────────


class TestGetTimezone:
    @respx.mock
    async def test_returns_timezone(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/timezone/json").mock(
            return_value=Response(200, json=_MOCK_TIMEZONE_RESPONSE)
        )
        result = await get_timezone.ainvoke(
            {"location": "35.6762,139.6503", "timestamp": 1700000000}
        )
        assert "Japan Standard Time" in result
        assert "Asia/Tokyo" in result
        assert "+9.0h" in result

    @respx.mock
    async def test_geocodes_text_location(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
            return_value=Response(200, json=_MOCK_GEOCODE_RESPONSE)
        )
        respx.get("https://maps.googleapis.com/maps/api/timezone/json").mock(
            return_value=Response(200, json=_MOCK_TIMEZONE_RESPONSE)
        )
        result = await get_timezone.ainvoke({"location": "Tokyo, Japan"})
        assert "Japan Standard Time" in result

    @respx.mock
    async def test_geocode_fails_returns_message(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
            return_value=Response(200, json={"status": "ZERO_RESULTS", "results": []})
        )
        result = await get_timezone.ainvoke({"location": "Nonexistent"})
        assert "Could not geocode" in result

    @respx.mock
    async def test_api_status_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/timezone/json").mock(
            return_value=Response(200, json={"status": "INVALID_REQUEST"})
        )
        result = await get_timezone.ainvoke(
            {"location": "35.6762,139.6503", "timestamp": 1700000000}
        )
        assert "INVALID_REQUEST" in result

    @respx.mock
    async def test_http_error_returns_message(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/timezone/json").mock(
            return_value=Response(500, text="Server Error")
        )
        result = await get_timezone.ainvoke(
            {"location": "35.6762,139.6503", "timestamp": 1700000000}
        )
        assert "error" in result.lower()
        assert "500" in result

    @respx.mock
    async def test_default_timestamp(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        route = respx.get("https://maps.googleapis.com/maps/api/timezone/json").mock(
            return_value=Response(200, json=_MOCK_TIMEZONE_RESPONSE)
        )
        await get_timezone.ainvoke({"location": "35.6762,139.6503"})
        # Should have been called with a timestamp param
        assert "timestamp" in str(route.calls[0].request.url)


# ── _format_place extended fields ────────────────────────────────────────


class TestFormatPlaceExtended:
    def test_with_all_optional_fields(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        place = {
            "displayName": {"text": "Ramen Shop"},
            "formattedAddress": "1-2-3 Shinjuku, Tokyo",
            "rating": 4.5,
            "userRatingCount": 300,
            "priceLevel": "PRICE_LEVEL_INEXPENSIVE",
            "types": ["restaurant", "food", "point_of_interest"],
            "businessStatus": "OPERATIONAL",
            "location": {"latitude": 35.69, "longitude": 139.70},
            "googleMapsUri": "https://maps.google.com/place/123",
            "websiteUri": "https://ramen.example.com",
            "editorialSummary": {"text": "Best tonkotsu ramen in Shinjuku"},
            "currentOpeningHours": {
                "weekdayDescriptions": ["Monday: 11:00 AM – 10:00 PM"]
            },
            "photos": [{"name": "places/abc/photos/def"}],
        }
        result = _format_place(place)
        assert "Ramen Shop" in result
        assert "1-2-3 Shinjuku" in result
        assert "4.5/5" in result
        assert "$" in result
        assert "OPERATIONAL" in result
        assert "Best tonkotsu" in result
        assert "Monday" in result
        assert "maps.google.com" in result
        assert "ramen.example.com" in result
        assert "35.69,139.7" in result

    def test_with_editorial_string(self):
        """editorialSummary as a plain string is passed through."""
        place = {
            "displayName": {"text": "Test"},
            "editorialSummary": "Already a string",
        }
        result = _format_place(place)
        assert "Test" in result

    def test_name_fallback_to_name_key(self):
        place = {"name": "Direct Name"}
        result = _format_place(place)
        assert "Direct Name" in result


# ── Request error paths ──────────────────────────────────────────────────


class TestRequestErrors:
    @respx.mock
    async def test_nearby_request_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchNearby").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await search_places_nearby.ainvoke(
            {"location": "38.0,-0.5", "place_type": "gym"}
        )
        assert "could not reach" in result.lower()

    @respx.mock
    async def test_text_search_request_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await search_places_text.ainvoke({"query": "test"})
        assert "could not reach" in result.lower()

    @respx.mock
    async def test_directions_request_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/directions/json").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await get_directions.ainvoke({"origin": "A", "destination": "B"})
        assert "could not reach" in result.lower()

    @respx.mock
    async def test_distance_matrix_request_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/distancematrix/json").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await get_distance_matrix.ainvoke(
            {"origins": "A", "destinations": "B"}
        )
        assert "could not reach" in result.lower()

    @respx.mock
    async def test_compute_route_request_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await compute_route.ainvoke({"origin": "A", "destination": "B"})
        assert "could not reach" in result.lower()

    @respx.mock
    async def test_timezone_request_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.get("https://maps.googleapis.com/maps/api/timezone/json").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await get_timezone.ainvoke(
            {"location": "35.6762,139.6503", "timestamp": 1700000000}
        )
        assert "could not reach" in result.lower()

    @respx.mock
    async def test_optimize_route_request_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await optimize_day_route.ainvoke(
            {"stops": "A, B", "start_location": "Hotel"}
        )
        assert "could not reach" in result.lower()
