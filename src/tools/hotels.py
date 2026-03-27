"""Hotel search tool using the Amadeus Hotel API.

Searches for hotels by city IATA code, returns pricing when available.
Shares OAuth2 token management with the flights module.
"""

import os

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from src.tools.flights import _get_amadeus_token


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def _search_hotels_api(
    city_code: str,
    check_in: str,
    check_out: str,
    adults: int,
) -> list[dict]:
    """Search for hotels and their offers in a city."""
    token = await _get_amadeus_token()
    base = os.environ["AMADEUS_BASE_URL"]

    async with httpx.AsyncClient() as client:
        # Step 1: Get hotel IDs for the city
        resp = await client.get(
            f"{base}/v1/reference-data/locations/hotels/by-city",
            headers={"Authorization": f"Bearer {token}"},
            params={"cityCode": city_code, "radius": 20, "radiusUnit": "KM"},
            timeout=15.0,
        )
        if resp.status_code == 401:
            from src.tools.flights import _token_cache
            _token_cache.clear()
            raise httpx.HTTPStatusError(
                "Token expired", request=resp.request, response=resp
            )
        resp.raise_for_status()
        hotels = resp.json().get("data", [])

        if not hotels:
            return []

        # Take top 10 hotel IDs for offer search
        hotel_ids = [h["hotelId"] for h in hotels[:10]]

        # Step 2: Get offers (pricing) for those hotels
        resp2 = await client.get(
            f"{base}/v3/shopping/hotel-offers",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "hotelIds": ",".join(hotel_ids),
                "checkInDate": check_in,
                "checkOutDate": check_out,
                "adults": adults,
                "currency": "USD",
            },
            timeout=20.0,
        )
        if resp2.status_code == 401:
            from src.tools.flights import _token_cache
            _token_cache.clear()
            raise httpx.HTTPStatusError(
                "Token expired", request=resp2.request, response=resp2
            )
        resp2.raise_for_status()
        return resp2.json().get("data", [])


@tool
async def search_hotels(
    city_code: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 1,
) -> str:
    """Search for hotels in a city with real pricing. Returns hotel name,
    star rating, price per night, total price, and amenities.

    Call lookup_iata_code first if you have a city name instead of a code.

    Args:
        city_code: IATA city code (e.g., "TYO" for Tokyo, "PAR" for Paris)
        check_in_date: Check-in date in YYYY-MM-DD format
        check_out_date: Check-out date in YYYY-MM-DD format
        adults: Number of adult guests (default 1)
    """
    offers = await _search_hotels_api(
        city_code=city_code.upper().strip(),
        check_in=check_in_date,
        check_out=check_out_date,
        adults=adults,
    )

    if not offers:
        return (
            f"No hotel offers found in {city_code} "
            f"for {check_in_date} to {check_out_date}."
        )

    results = [
        f"Hotels in {city_code} ({check_in_date} to {check_out_date}):\n"
    ]

    for i, hotel_data in enumerate(offers[:5], 1):
        hotel = hotel_data.get("hotel", {})
        name = hotel.get("name", "Unknown Hotel")
        rating = hotel.get("rating", "N/A")

        offer = hotel_data.get("offers", [{}])[0]
        price_info = offer.get("price", {})
        total = price_info.get("total", "N/A")
        currency = price_info.get("currency", "USD")

        # Calculate nightly from total and stay duration
        check_in_room = offer.get("checkInDate", check_in_date)
        check_out_room = offer.get("checkOutDate", check_out_date)

        room = offer.get("room", {})
        room_type = room.get("typeEstimated", {})
        bed_type = room_type.get("bedType", "N/A")
        beds = room_type.get("beds", "N/A")
        category = room_type.get("category", "STANDARD")

        results.append(
            f"  {i}. {name}\n"
            f"     Rating: {'★' * int(rating) if rating != 'N/A' else 'N/A'} "
            f"({rating} stars)\n"
            f"     Total: ${total} {currency}\n"
            f"     Room: {category} — {beds} {bed_type} bed(s)\n"
            f"     Dates: {check_in_room} to {check_out_room}"
        )
        results.append("")

    return "\n".join(results)
