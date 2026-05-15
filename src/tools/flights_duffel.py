"""Flight tools using the Duffel Flights API.

Implements the Duffel search and pricing flow:
  1. Create Offer Request — POST /air/offer_requests
  2. Get Single Offer     — GET /air/offers/:id (latest price)

Plus convenience wrappers:
  3. search_cheapest_flight_in_month — multi-date sampling
  4. get_cheapest_flight             — returns single cheapest offer

And airport discovery:
  5. search_nearby_airports — GET /places/suggestions (by lat/lng)

Authenticates via Bearer token. Uses the Duffel test environment by default
(test tokens start with duffel_test_).

Best practices applied (per Duffel docs):
  - Always pass cabin_class to reduce results and speed up search
  - Set max_connections to limit payload size
  - Use supplier_timeout query parameter for speed/coverage trade-off
  - Include Accept-Encoding: gzip
  - Re-fetch offer by ID before presenting final price
"""

import asyncio
import calendar
import os
from datetime import date

import httpx
from langchain_core.tools import tool
from tenacity import (
    RetryError,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


# ── Configuration ────────────────────────────────────────────────────────

_DUFFEL_BASE_URL = os.environ.get("DUFFEL_BASE_URL", "https://api.duffel.com")
_SUPPLIER_TIMEOUT = int(os.environ.get("DUFFEL_SUPPLIER_TIMEOUT", "15000"))

# Cap concurrent outbound Duffel requests to prevent thundering herd.
_duffel_semaphore: asyncio.Semaphore = asyncio.Semaphore(5)


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_headers() -> dict[str, str]:
    """Build required Duffel API headers."""
    token = os.environ.get("DUFFEL_ACCESS_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip",
    }


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on transient HTTP errors (429, 500+)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


def _parse_duffel_error(response: httpx.Response) -> str:
    """Extract user-friendly error message from Duffel error response."""
    try:
        body = response.json()
        errors = body.get("errors", [])
        if errors:
            return errors[0].get("message", errors[0].get("title", "Unknown error"))
    except Exception:
        pass
    return f"Duffel API error ({response.status_code})"


def _parse_iso_duration(duration: str | None) -> tuple[str, int]:
    """Parse ISO 8601 duration (e.g., PT7H30M) to readable string and minutes."""
    if not duration:
        return "N/A", 0
    dur_str = duration.replace("PT", "").replace("H", "h ").replace("M", "m").strip()
    dur_mins = 0
    dur_clean = duration.replace("PT", "")
    if "H" in dur_clean:
        parts = dur_clean.split("H")
        dur_mins += int(parts[0]) * 60
        dur_clean = parts[1]
    if "M" in dur_clean:
        m_val = dur_clean.replace("M", "").strip()
        dur_mins += int(m_val) if m_val else 0
    return dur_str, dur_mins


def _map_cabin_class(travel_class: str) -> str | None:
    """Map Wanderlisted cabin class values to Duffel's accepted values."""
    mapping = {
        "ECONOMY": "economy",
        "PREMIUM_ECONOMY": "premium_economy",
        "BUSINESS": "business",
        "FIRST": "first",
    }
    return mapping.get(travel_class.upper()) if travel_class else None


def _format_baggage(baggages: list[dict]) -> str:
    """Format baggage info from segment passengers."""
    parts = []
    for bag in baggages:
        bag_type = bag.get("type", "").replace("_", " ")
        qty = bag.get("quantity", 0)
        parts.append(f"{qty} {bag_type}")
    return ", ".join(parts) if parts else "Unknown"


def _format_conditions(conditions: dict | None) -> str:
    """Format change/refund conditions for agent output."""
    if not conditions:
        return "Flexibility: Unknown"

    parts = []

    change = conditions.get("change_before_departure")
    if change is None:
        parts.append("Change: Unknown")
    elif not change.get("allowed"):
        parts.append("Change: Not allowed")
    elif change.get("penalty_amount") and float(change["penalty_amount"]) > 0:
        parts.append(
            f"Change: {change['penalty_currency']} {change['penalty_amount']} fee"
        )
    else:
        parts.append("Change: Free")

    refund = conditions.get("refund_before_departure")
    if refund is None:
        parts.append("Refund: Unknown")
    elif not refund.get("allowed"):
        parts.append("Refund: Not allowed")
    elif refund.get("penalty_amount") and float(refund["penalty_amount"]) > 0:
        parts.append(
            f"Refund: {refund['penalty_currency']} {refund['penalty_amount']} penalty"
        )
    else:
        parts.append("Refund: Free")

    return " | ".join(parts)


def _format_offer(offer: dict, index: int) -> list[str]:
    """Format a single Duffel offer into readable lines."""
    lines = []
    total_amount = offer.get("total_amount", "?")
    total_currency = offer.get("total_currency", "USD")

    owner = offer.get("owner", {})
    airline_name = owner.get("name", "Unknown")
    airline_code = owner.get("iata_code", "??")

    slices = offer.get("slices", [])
    if not slices:
        lines.append(
            f"  {index}. {airline_code} ({airline_name}) — {total_currency} {total_amount}"
        )
        return lines

    # Outbound slice
    outbound = slices[0]
    segments = outbound.get("segments", [])
    if not segments:
        lines.append(
            f"  {index}. {airline_code} ({airline_name}) — {total_currency} {total_amount}"
        )
        return lines

    first_seg = segments[0]
    last_seg = segments[-1]

    carrier = first_seg.get("operating_carrier", {})
    carrier_code = carrier.get("iata_code", airline_code)
    flight_num = first_seg.get("operating_carrier_flight_number", "")
    full_flight = f"{carrier_code}{flight_num}"

    dep_airport = first_seg.get("origin", {}).get("iata_code", "???")
    arr_airport = last_seg.get("destination", {}).get("iata_code", "???")
    departure = first_seg.get("departing_at", "")
    arrival = last_seg.get("arriving_at", "")

    slice_duration = outbound.get("duration")
    dur_str, dur_mins = _parse_iso_duration(slice_duration)
    stops = len(segments) - 1

    # Cabin and baggage from first segment's first passenger
    cabin = "economy"
    baggage_str = ""
    seg_passengers = first_seg.get("passengers", [])
    if seg_passengers:
        cabin = seg_passengers[0].get("cabin_class_marketing_name") or seg_passengers[
            0
        ].get("cabin_class", "economy")
        baggages = seg_passengers[0].get("baggages", [])
        if baggages:
            baggage_str = f"\n     Bags included: {_format_baggage(baggages)}"

    lines.append(
        f"  {index}. {full_flight} ({airline_name}) — {total_currency} {total_amount}\n"
        f"     Carrier: {carrier_code} | Flight: {flight_num}\n"
        f"     Departure airport: {dep_airport} | Arrival airport: {arr_airport}\n"
        f"     Depart: {departure} → Arrive: {arrival}\n"
        f"     Duration: {dur_str} ({dur_mins} minutes) · "
        f"{'Non-stop' if stops == 0 else f'{stops} stop(s)'}\n"
        f"     Cabin: {cabin}{baggage_str}"
    )

    # Conditions
    conditions = offer.get("conditions")
    if conditions:
        lines.append(f"     {_format_conditions(conditions)}")

    # Return slice
    if len(slices) > 1:
        ret = slices[1]
        ret_segs = ret.get("segments", [])
        if ret_segs:
            ret_dep_airport = ret_segs[0].get("origin", {}).get("iata_code", "???")
            ret_arr_airport = (
                ret_segs[-1].get("destination", {}).get("iata_code", "???")
            )
            ret_dep = ret_segs[0].get("departing_at", "")
            ret_arr = ret_segs[-1].get("arriving_at", "")
            ret_dur_str, _ = _parse_iso_duration(ret.get("duration"))
            ret_stops = len(ret_segs) - 1
            lines.append(
                f"     Return: {ret_dep_airport} → {ret_arr_airport}\n"
                f"     Return depart: {ret_dep} → Return arrive: {ret_arr}\n"
                f"     Return duration: {ret_dur_str} · "
                f"{'non-stop' if ret_stops == 0 else f'{ret_stops} stop(s)'}"
            )

    lines.append("")
    return lines


# ── API Calls ────────────────────────────────────────────────────────────


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception(_is_retryable),
)
async def _create_offer_request(
    slices: list[dict],
    passengers: list[dict],
    cabin_class: str | None = None,
    max_connections: int | None = None,
    supplier_timeout: int | None = None,
) -> dict:
    """Create an offer request (search for flights)."""
    payload: dict = {
        "data": {
            "slices": slices,
            "passengers": passengers,
        }
    }
    if cabin_class:
        payload["data"]["cabin_class"] = cabin_class
    if max_connections is not None:
        payload["data"]["max_connections"] = max_connections

    timeout_ms = supplier_timeout or _SUPPLIER_TIMEOUT
    url = f"{_DUFFEL_BASE_URL}/air/offer_requests?return_offers=true&supplier_timeout={timeout_ms}"

    async with _duffel_semaphore:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=30.0,
            )
            if response.status_code >= 400:
                msg = _parse_duffel_error(response)
                if _is_retryable(
                    httpx.HTTPStatusError(
                        "", request=response.request, response=response
                    )
                ):
                    response.raise_for_status()
                raise httpx.HTTPStatusError(
                    msg, request=response.request, response=response
                )
            return response.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception(_is_retryable),
)
async def _get_offer(offer_id: str) -> dict:
    """Get a single offer by ID for the latest price."""
    url = f"{_DUFFEL_BASE_URL}/air/offers/{offer_id}"

    async with _duffel_semaphore:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=_get_headers(),
                timeout=15.0,
            )
            if response.status_code >= 400:
                msg = _parse_duffel_error(response)
                if _is_retryable(
                    httpx.HTTPStatusError(
                        "", request=response.request, response=response
                    )
                ):
                    response.raise_for_status()
                raise httpx.HTTPStatusError(
                    msg, request=response.request, response=response
                )
            return response.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception(_is_retryable),
)
async def _get_place_suggestions(
    latitude: float, longitude: float, radius_meters: int
) -> dict:
    """Find airports near a geographic point."""
    url = f"{_DUFFEL_BASE_URL}/places/suggestions?lat={latitude}&lng={longitude}&rad={radius_meters}"

    async with _duffel_semaphore:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=_get_headers(),
                timeout=10.0,
            )
            if response.status_code >= 400:
                msg = _parse_duffel_error(response)
                if _is_retryable(
                    httpx.HTTPStatusError(
                        "", request=response.request, response=response
                    )
                ):
                    response.raise_for_status()
                raise httpx.HTTPStatusError(
                    msg, request=response.request, response=response
                )
            return response.json()


# ── Builders ─────────────────────────────────────────────────────────────


def _build_slices(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None,
) -> list[dict]:
    """Build slices array for an offer request."""
    slices = [
        {
            "origin": origin.upper().strip(),
            "destination": destination.upper().strip(),
            "departure_date": departure_date,
        }
    ]
    if return_date:
        slices.append(
            {
                "origin": destination.upper().strip(),
                "destination": origin.upper().strip(),
                "departure_date": return_date,
            }
        )
    return slices


def _build_passengers(adults: int, children: int, infants: int) -> list[dict]:
    """Build passengers array for an offer request."""
    passengers: list[dict] = []
    for _ in range(adults):
        passengers.append({"type": "adult"})
    for _ in range(children):
        # Children: use age 8 as representative (ages 2-11)
        passengers.append({"age": 8})
    for _ in range(infants):
        passengers.append({"age": 0})
    return passengers


# ── Tool: search_flights ─────────────────────────────────────────────────


@tool
async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
    return_date: str = "",
    children: int = 0,
    infants: int = 0,
    travel_class: str = "",
    non_stop: bool = False,
) -> str:
    """Search for flights between two airports or cities. Returns top 5 options
    with price, airline, duration, stops, baggage, and flexibility conditions.

    Accepts both airport codes (JFK, NRT) and city codes (NYC, LON, TYO).

    Args:
        origin: Origin IATA airport or city code (e.g., "NYC", "JFK", "LHR")
        destination: Destination IATA airport or city code (e.g., "TYO", "NRT", "CDG")
        departure_date: Departure date in YYYY-MM-DD format
        adults: Number of adult passengers 12+ years (default 1, max 9)
        return_date: Optional return date in YYYY-MM-DD format for round trips
        children: Number of child passengers 2-11 years (default 0)
        infants: Number of infant passengers under 2 years (default 0)
        travel_class: Cabin class filter — ECONOMY, PREMIUM_ECONOMY, BUSINESS, or FIRST (default: all)
        non_stop: If true, only return non-stop flights (default false)
    """
    slices = _build_slices(origin, destination, departure_date, return_date or None)
    passengers = _build_passengers(adults, children, infants)
    cabin_class = _map_cabin_class(travel_class) if travel_class else None
    max_connections = 0 if non_stop else 1

    try:
        data = await _create_offer_request(
            slices=slices,
            passengers=passengers,
            cabin_class=cabin_class,
            max_connections=max_connections,
        )
    except (httpx.HTTPStatusError, RetryError) as exc:
        msg = str(exc)
        if hasattr(exc, "response"):
            msg = _parse_duffel_error(exc.response)
        return (
            f"Flight search error: {msg}. "
            f"Unable to search flights from {origin} to {destination} on {departure_date}. "
            f"Please try again later or adjust your search criteria."
        )

    offers = data.get("data", {}).get("offers", [])
    if not offers:
        return f"No flights found from {origin} to {destination} on {departure_date}."

    # Sort by total_amount and take top 5
    offers.sort(key=lambda o: float(o.get("total_amount", "999999")))
    top_offers = offers[:5]

    results = [f"Top {len(top_offers)} flights from {origin} → {destination}:\n"]
    for i, offer in enumerate(top_offers, 1):
        results.extend(_format_offer(offer, i))

    return "\n".join(results)


# ── Tool: confirm_flight_price ───────────────────────────────────────────


@tool
async def confirm_flight_price(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
    return_date: str = "",
    children: int = 0,
    infants: int = 0,
    travel_class: str = "",
    non_stop: bool = False,
    offer_index: int = 1,
) -> str:
    """Confirm the current price and availability of a flight offer. Retrieves
    the latest price directly from the airline via Duffel.

    Prices fluctuate constantly — this verifies the offer is still available at
    the listed price. Returns confirmed pricing with conditions.

    Args:
        origin: Origin IATA airport or city code
        destination: Destination IATA airport or city code
        departure_date: Departure date YYYY-MM-DD
        adults: Number of adult passengers (default 1)
        return_date: Optional return date YYYY-MM-DD
        children: Number of children 2-11 years (default 0)
        infants: Number of infants under 2 (default 0)
        travel_class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, or FIRST
        non_stop: Only non-stop flights (default false)
        offer_index: Which offer to confirm (1-based, from search results, default 1)
    """
    # First, search to get offer IDs
    slices = _build_slices(origin, destination, departure_date, return_date or None)
    passengers = _build_passengers(adults, children, infants)
    cabin_class = _map_cabin_class(travel_class) if travel_class else None
    max_connections = 0 if non_stop else 1

    try:
        data = await _create_offer_request(
            slices=slices,
            passengers=passengers,
            cabin_class=cabin_class,
            max_connections=max_connections,
        )
    except (httpx.HTTPStatusError, RetryError) as exc:
        msg = str(exc)
        if hasattr(exc, "response"):
            msg = _parse_duffel_error(exc.response)
        return f"Flight search failed: {msg}. Cannot confirm price."

    offers = data.get("data", {}).get("offers", [])
    if not offers:
        return f"No flights found from {origin} to {destination} on {departure_date}."

    # Sort by price to match search_flights ordering
    offers.sort(key=lambda o: float(o.get("total_amount", "999999")))

    if offer_index < 1 or offer_index > len(offers):
        return f"Invalid offer_index {offer_index}. Found {len(offers)} offers (1-{len(offers)})."

    selected = offers[offer_index - 1]
    offer_id = selected.get("id")
    original_price = selected.get("total_amount", "?")

    # Re-fetch offer for the latest price
    try:
        refreshed_data = await _get_offer(offer_id)
    except (httpx.HTTPStatusError, RetryError) as exc:
        msg = str(exc)
        if hasattr(exc, "response"):
            msg = _parse_duffel_error(exc.response)
        return (
            f"Price confirmation failed: {msg}. "
            f"The offer may no longer be available. Try searching again."
        )

    refreshed = refreshed_data.get("data", {})
    if not refreshed:
        return "Price confirmation returned empty data — the offer may have expired."

    confirmed_price = refreshed.get("total_amount", "?")
    currency = refreshed.get("total_currency", "USD")

    results = ["✅ Price confirmed! This offer is available.\n"]
    results.extend(_format_offer(refreshed, offer_index))
    results.append(f"  Confirmed total: {currency} {confirmed_price}")

    # Note price change
    if original_price != confirmed_price and original_price != "?":
        results.append(
            f"  ⚠ Price changed: {currency} {original_price} → {currency} {confirmed_price}"
        )

    # Payment requirements
    payment_reqs = refreshed.get("payment_requirements", {})
    if payment_reqs:
        if not payment_reqs.get("requires_instant_payment"):
            pay_by = payment_reqs.get("payment_required_by", "")
            results.append(
                f"  💡 This offer can be held without immediate payment (pay by: {pay_by})"
            )

    return "\n".join(results)


# ── Tool: get_cheapest_flight ────────────────────────────────────────────


@tool
async def get_cheapest_flight(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
    return_date: str = "",
    children: int = 0,
    infants: int = 0,
    travel_class: str = "",
    non_stop: bool = False,
) -> str:
    """Find the single cheapest flight on a specific date.

    Args:
        origin: Origin IATA airport or city code
        destination: Destination IATA airport or city code
        departure_date: Departure date YYYY-MM-DD
        adults: Number of adults (default 1)
        return_date: Optional return date YYYY-MM-DD
        children: Number of children 2-11 (default 0)
        infants: Number of infants under 2 (default 0)
        travel_class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, or FIRST
        non_stop: Only non-stop flights
    """
    slices = _build_slices(origin, destination, departure_date, return_date or None)
    passengers = _build_passengers(adults, children, infants)
    cabin_class = _map_cabin_class(travel_class) if travel_class else None
    max_connections = 0 if non_stop else 1

    try:
        data = await _create_offer_request(
            slices=slices,
            passengers=passengers,
            cabin_class=cabin_class,
            max_connections=max_connections,
        )
    except (httpx.HTTPStatusError, RetryError) as exc:
        msg = str(exc)
        if hasattr(exc, "response"):
            msg = _parse_duffel_error(exc.response)
        return f"Flight search failed: {msg}."

    offers = data.get("data", {}).get("offers", [])
    if not offers:
        return f"No flights found from {origin} to {destination} on {departure_date}."

    cheapest = min(offers, key=lambda o: float(o.get("total_amount", "999999")))

    results = [f"Cheapest flight {origin} → {destination} on {departure_date}:\n"]
    results.extend(_format_offer(cheapest, 1))
    return "\n".join(results)


# ── Tool: search_cheapest_flight_in_month ────────────────────────────────


@tool
async def search_cheapest_flight_in_month(
    origin: str,
    destination: str,
    year: int,
    month: int,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    travel_class: str = "",
    non_stop: bool = False,
) -> str:
    """Search multiple dates within a month to find the cheapest flights.
    Samples dates across the month and returns the best options.

    Args:
        origin: Origin IATA airport or city code
        destination: Destination IATA airport or city code
        year: Year (e.g., 2026)
        month: Month number (1-12)
        adults: Number of adults (default 1)
        children: Number of children 2-11 (default 0)
        infants: Number of infants under 2 (default 0)
        travel_class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, or FIRST
        non_stop: Only non-stop flights
    """
    _, days_in_month = calendar.monthrange(year, month)
    today = date.today()
    sample_days = [1, 8, 15, 22]
    sample_dates = []
    for day in sample_days:
        if day > days_in_month:
            continue
        d = date(year, month, day)
        if d > today:
            sample_dates.append(d.isoformat())

    if not sample_dates:
        return f"No future dates available in {year}-{month:02d}."

    passengers = _build_passengers(adults, children, infants)
    cabin_class = _map_cabin_class(travel_class) if travel_class else None
    max_connections = 0 if non_stop else 1

    # Use shorter timeout for multi-date sampling
    all_offers: list[tuple[str, dict]] = []
    for dep_date in sample_dates:
        slices = _build_slices(origin, destination, dep_date, None)
        try:
            data = await _create_offer_request(
                slices=slices,
                passengers=passengers,
                cabin_class=cabin_class,
                max_connections=max_connections,
                supplier_timeout=10000,
            )
            for offer in data.get("data", {}).get("offers", []):
                all_offers.append((dep_date, offer))
        except (httpx.HTTPStatusError, RetryError):
            continue

    if not all_offers:
        return f"No flights found from {origin} to {destination} in {year}-{month:02d}."

    # Sort by price and return top 5
    all_offers.sort(key=lambda x: float(x[1].get("total_amount", "999999")))
    top = all_offers[:5]

    results = [f"Cheapest flights {origin} → {destination} in {year}-{month:02d}:\n"]
    for i, (_dep_date, offer) in enumerate(top, 1):
        results.extend(_format_offer(offer, i))

    return "\n".join(results)


# ── Tool: search_nearby_airports ─────────────────────────────────────────


@tool
async def search_nearby_airports(
    latitude: float,
    longitude: float,
    radius_km: int = 100,
) -> str:
    """Find airports near a geographic location. Useful when a destination
    doesn't have its own airport, or to discover alternative airports.

    Args:
        latitude: Latitude of the location (e.g., 37.13 for Lagos, Portugal)
        longitude: Longitude of the location (e.g., -8.67 for Lagos, Portugal)
        radius_km: Search radius in kilometers (default 100, max 200)
    """
    radius_meters = min(radius_km, 200) * 1000

    try:
        data = await _get_place_suggestions(latitude, longitude, radius_meters)
    except (httpx.HTTPStatusError, RetryError) as exc:
        msg = str(exc)
        if hasattr(exc, "response"):
            msg = _parse_duffel_error(exc.response)
        return f"Airport search failed: {msg}."

    places = data.get("data", [])
    airports = [p for p in places if p.get("type") == "airport"]

    if not airports:
        return f"No airports found within {radius_km}km of ({latitude}, {longitude})."

    results = [f"Airports within {radius_km}km of ({latitude}, {longitude}):\n"]
    for i, airport in enumerate(airports, 1):
        iata = airport.get("iata_code", "???")
        name = airport.get("name", "Unknown")
        city = airport.get("city_name", "")
        country = airport.get("iata_country_code", "")
        results.append(f"  {i}. {iata} — {name} ({city}, {country})")

    return "\n".join(results)
