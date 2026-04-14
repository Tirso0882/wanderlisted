"""Unit tests for activities tool — mocked Google Places API responses."""

import respx
from httpx import Response

from src.tools.activities import search_activities


_MOCK_PLACES_RESPONSE = {
    "places": [
        {
            "displayName": {"text": "Ichiran Shibuya"},
            "formattedAddress": "1-22-7 Jinnan, Shibuya, Tokyo",
            "rating": 4.5,
            "userRatingCount": 3200,
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "types": ["restaurant", "food", "point_of_interest"],
            "editorialSummary": {"text": "Famous tonkotsu ramen chain."},
            "websiteUri": "https://ichiran.com",
            "googleMapsUri": "https://maps.google.com/?cid=12345",
            "photos": [{"name": "places/abc/photos/xyz"}],
        }
    ]
}


class TestActivitiesMocked:
    @respx.mock
    async def test_returns_formatted_results(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(200, json=_MOCK_PLACES_RESPONSE)
        )

        result = await search_activities.ainvoke(
            {
                "city": "Tokyo, Japan",
                "category": "food",
                "query": "ramen",
                "limit": 3,
            }
        )

        assert "Ichiran Shibuya" in result
        assert "4.5/5" in result
        assert "$$" in result

    @respx.mock
    async def test_includes_google_maps_link(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(200, json=_MOCK_PLACES_RESPONSE)
        )

        result = await search_activities.ainvoke(
            {
                "city": "Tokyo, Japan",
                "category": "food",
            }
        )

        assert "maps.google.com" in result

    @respx.mock
    async def test_includes_photo_url(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(200, json=_MOCK_PLACES_RESPONSE)
        )

        result = await search_activities.ainvoke(
            {
                "city": "Tokyo, Japan",
                "category": "food",
            }
        )

        assert "Photo:" in result
        assert "places/abc/photos/xyz" in result

    @respx.mock
    async def test_no_results(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(200, json={"places": []})
        )

        result = await search_activities.ainvoke(
            {
                "city": "Nowhere, Atlantis",
                "category": "sightseeing",
            }
        )

        assert "No sightseeing activities found" in result

    @respx.mock
    async def test_limit_clamped(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        route = respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(200, json=_MOCK_PLACES_RESPONSE)
        )

        await search_activities.ainvoke(
            {
                "city": "Tokyo, Japan",
                "category": "food",
                "limit": 50,  # should be clamped to 10
            }
        )

        import json

        body = json.loads(route.calls[0].request.content)
        assert body["maxResultCount"] == 10

    @respx.mock
    async def test_all_categories_produce_query(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=Response(200, json={"places": []})
        )

        for cat in [
            "sightseeing",
            "food",
            "outdoor",
            "culture",
            "shopping",
            "nightlife",
        ]:
            result = await search_activities.ainvoke(
                {
                    "city": "Paris, France",
                    "category": cat,
                }
            )
            # Should not crash — returns "No X activities found"
            assert "activities found" in result.lower() or cat.lower() in result.lower()
