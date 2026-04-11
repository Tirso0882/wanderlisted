"""Flight search tool using the Amadeus Flight Offers API.

Authenticates via OAuth2 client credentials, then searches for flight offers.
Uses the Amadeus test environment by default.
"""

import os

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

_token_cache: dict[str, str] = {}


async def _get_amadeus_token() -> str:
    """Obtain or reuse an Amadeus OAuth2 access token."""
    if "access_token" in _token_cache:
        return _token_cache["access_token"]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{os.environ['AMADEUS_BASE_URL']}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": os.environ["AMADEUS_API_KEY"],
                "client_secret": os.environ["AMADEUS_API_SECRET"],
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

    _token_cache["access_token"] = data["access_token"]
    return data["access_token"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def _search_flights_api(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int,
    return_date: str | None,
) -> dict:
    """Call Amadeus flight offers search with retry logic."""
    token = await _get_amadeus_token()
    params: dict = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": departure_date,
        "adults": adults,
        "max": 5,
        "currencyCode": "USD",
    }
    if return_date:
        params["returnDate"] = return_date

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{os.environ['AMADEUS_BASE_URL']}/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=15.0,
        )
        # Token expired — clear cache and retry
        if response.status_code == 401:
            _token_cache.clear()
            raise httpx.HTTPStatusError(
                "Token expired", request=response.request, response=response
            )
        response.raise_for_status()
        return response.json()


@tool
async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
    return_date: str = "",
) -> str:
    """Search for flights between two airports. Returns top 5 options with
    price, airline, duration, and number of stops.

    Call lookup_iata_code first if you have a city name instead of an IATA code.

    Args:
        origin: Origin IATA code (e.g., "SEA", "JFK", "LHR")
        destination: Destination IATA code (e.g., "NRT", "CDG", "SYD")
        departure_date: Departure date in YYYY-MM-DD format
        adults: Number of adult passengers (default 1)
        return_date: Optional return date in YYYY-MM-DD format for round trips
    """
    data = await _search_flights_api(
        origin=origin.upper().strip(),
        destination=destination.upper().strip(),
        departure_date=departure_date,
        adults=adults,
        return_date=return_date if return_date else None,
    )

    offers = data.get("data", [])
    if not offers:
        return (
            f"No flights found from {origin} to {destination} "
            f"on {departure_date}."
        )

    results = [f"Top {len(offers)} flights from {origin} → {destination}:\n"]

    for i, offer in enumerate(offers, 1):
        price = offer["price"]["total"]
        currency = offer["price"].get("currency", "USD")

        segments = offer["itineraries"][0]["segments"]
        first_seg = segments[0]
        last_seg = segments[-1]
        airline = first_seg["carrierCode"]
        flight_num = f"{airline}{first_seg['number']}"
        dep_airport = first_seg["departure"]["iataCode"]
        arr_airport = last_seg["arrival"]["iataCode"]
        departure = first_seg["departure"]["at"]
        arrival = last_seg["arrival"]["at"]
        duration = offer["itineraries"][0].get("duration", "N/A")
        stops = len(segments) - 1

        # Parse ISO 8601 duration to minutes and readable string
        dur_str = duration.replace("PT", "").replace("H", "h ").replace("M", "m")
        dur_mins = 0
        dur_clean = duration.replace("PT", "")
        if "H" in dur_clean:
            parts = dur_clean.split("H")
            dur_mins += int(parts[0]) * 60
            dur_clean = parts[1]
        if "M" in dur_clean:
            dur_mins += int(dur_clean.replace("M", "") or 0)

        results.append(
            f"  {i}. {flight_num} ({airline}) — ${price} {currency}\n"
            f"     Carrier: {airline} | Flight: {first_seg['number']}\n"
            f"     Departure airport: {dep_airport} | Arrival airport: {arr_airport}\n"
            f"     Depart: {departure} → Arrive: {arrival}\n"
            f"     Duration: {dur_str} ({dur_mins} minutes) · "
            f"{'Non-stop' if stops == 0 else f'{stops} stop(s)'}\n"
            f"     Cabin class: economy"
        )

        # If round trip, show return leg
        if len(offer["itineraries"]) > 1:
            ret = offer["itineraries"][1]
            ret_segs = ret["segments"]
            ret_dep_airport = ret_segs[0]["departure"]["iataCode"]
            ret_arr_airport = ret_segs[-1]["arrival"]["iataCode"]
            ret_dep = ret_segs[0]["departure"]["at"]
            ret_arr = ret_segs[-1]["arrival"]["at"]
            ret_dur = ret.get("duration", "N/A").replace(
                "PT", ""
            ).replace("H", "h ").replace("M", "m")
            ret_stops = len(ret_segs) - 1
            results.append(
                f"     Return: {ret_dep_airport} → {ret_arr_airport}\n"
                f"     Return depart: {ret_dep} → Return arrive: {ret_arr}\n"
                f"     Return duration: {ret_dur} · "
                f"{'non-stop' if ret_stops == 0 else f'{ret_stops} stop(s)'}"
            )

        results.append("")

    return "\n".join(results)
