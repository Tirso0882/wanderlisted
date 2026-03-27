"""Activity and attraction search tool using Google Places API (New).

Searches for things to do, restaurants, and attractions in a city.
Returns names, ratings, price levels, photos, and Google Maps links.
"""

import os

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

# Google Places "included types" — mapped from user-friendly category names.
# Ref: https://developers.google.com/maps/documentation/places/web-service/place-types
_CATEGORY_TYPES: dict[str, list[str]] = {
    "sightseeing": ["tourist_attraction", "landmark", "historical_landmark"],
    "food": ["restaurant", "cafe", "bakery"],
    "outdoor": ["park", "hiking_area", "national_park", "garden"],
    "culture": ["museum", "art_gallery", "performing_arts_theater"],
    "shopping": ["shopping_mall", "market", "clothing_store"],
    "nightlife": ["night_club", "bar", "cocktail_bar"],
}

# Fields we request (controls billing — only request what we use).
_FIELD_MASK = (
    "places.displayName,"
    "places.formattedAddress,"
    "places.rating,"
    "places.userRatingCount,"
    "places.priceLevel,"
    "places.types,"
    "places.editorialSummary,"
    "places.websiteUri,"
    "places.googleMapsUri,"
    "places.photos,"
    "places.currentOpeningHours"
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def _search_places_api(
    text_query: str,
    included_types: list[str],
    limit: int,
) -> dict:
    """Call Google Places Text Search (New) with retry."""
    api_key = os.environ["GOOGLE_MAPS_API_KEY"]

    body: dict = {
        "textQuery": text_query,
        "maxResultCount": limit,
        "languageCode": "en",
    }
    if included_types:
        # Text Search accepts includedType (singular) — one type per request.
        # Use the first type to narrow results; the text query handles the rest.
        body["includedType"] = included_types[0]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": _FIELD_MASK,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()


def _photo_url(photo: dict, max_width: int = 400) -> str:
    """Build a Google Places photo URL from a photo resource name."""
    api_key = os.environ["GOOGLE_MAPS_API_KEY"]
    name = photo.get("name", "")
    if not name:
        return ""
    return (
        f"https://places.googleapis.com/v1/{name}/media"
        f"?maxWidthPx={max_width}&key={api_key}"
    )


@tool
async def search_activities(
    city: str,
    category: str = "sightseeing",
    query: str = "",
    limit: int = 5,
) -> str:
    """Search for activities, attractions, and restaurants in a city.
    Returns names, ratings, price levels, addresses, and Google Maps links.

    Args:
        city: City and optionally country (e.g., "Tokyo, Japan", "Paris, France")
        category: One of: sightseeing, food, outdoor, culture, shopping, nightlife
        query: Optional specific search term (e.g., "ramen", "temple", "museum")
        limit: Number of results to return (1-10, default 5)
    """
    limit = max(1, min(limit, 10))
    types = _CATEGORY_TYPES.get(category.lower(), [])

    # Build the text query — e.g. "temple sightseeing in Tokyo, Japan"
    text_query = f"{query} {category}" if query else category
    text_query = f"{text_query} in {city}"

    data = await _search_places_api(
        text_query=text_query,
        included_types=types,
        limit=limit,
    )

    places = data.get("places", [])
    if not places:
        return f"No {category} activities found in {city}."

    price_labels = {
        "PRICE_LEVEL_FREE": "Free",
        "PRICE_LEVEL_INEXPENSIVE": "$",
        "PRICE_LEVEL_MODERATE": "$$",
        "PRICE_LEVEL_EXPENSIVE": "$$$",
        "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
    }

    results = [f"{category.title()} in {city}:\n"]

    for i, place in enumerate(places, 1):
        name = place.get("displayName", {}).get("text", "Unknown")
        rating = place.get("rating")
        reviews = place.get("userRatingCount", 0)
        price_level = place.get("priceLevel", "")
        summary = place.get("editorialSummary", {}).get("text", "")
        address = place.get("formattedAddress", "")
        website = place.get("websiteUri", "")
        maps_url = place.get("googleMapsUri", "")

        types_list = place.get("types", [])
        type_str = ", ".join(t.replace("_", " ").title() for t in types_list[:3])

        rating_str = f"{rating}/5 ({reviews:,} reviews)" if rating else "N/A"
        price_str = price_labels.get(price_level, "N/A")

        # Get first photo URL if available
        photos = place.get("photos", [])
        photo_url = _photo_url(photos[0]) if photos else ""

        entry = f"  {i}. {name}\n"
        entry += f"     Category: {type_str}\n"
        entry += f"     Rating: {rating_str} · Price: {price_str}\n"
        if address:
            entry += f"     Address: {address}\n"
        if summary:
            entry += f"     Description: {summary[:200]}\n"
        if website:
            entry += f"     Website: {website}\n"
        if maps_url:
            entry += f"     Google Maps: {maps_url}\n"
        if photo_url:
            entry += f"     Photo: {photo_url}\n"

        results.append(entry)

    return "\n".join(results)
