"""Hotel search tools using the Hotelbeds (HBX Group) Booking API.

Provides two LangChain tools:
  • search_hotels_hotelbeds  — Availability search (POST /hotels)
  • check_hotel_rate_hotelbeds — Rate verification + upselling (POST /checkrates)

Hotelbeds covers 250 K+ properties worldwide, strong on independents, boutiques,
and locally-owned hotels.  Prices returned are final (net
includes supplements and discounts).
"""

import hashlib
import os
import time

import httpx
from langchain_core.tools import tool
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from custom_logging import AppLogger

logger = AppLogger(logger_name="tools.hotels_hotelbeds", level="DEBUG")

_DEFAULT_BASE_URL = "https://api.test.hotelbeds.com"


# ── Authentication ────────────────────────────────────────────────────────


def _hotelbeds_headers() -> dict[str, str]:
    """Build authentication headers for Hotelbeds API.

    X-Signature = SHA256(apiKey + secret + unixTimestampInSeconds)
    """
    api_key = os.environ.get("HOTELBEDS_API_KEY", "")
    secret = os.environ.get("HOTELBEDS_API_SECRET", "")
    if not api_key or not secret:
        raise RuntimeError(
            "HOTELBEDS_API_KEY and HOTELBEDS_API_SECRET environment variables must be set"
        )
    timestamp = str(int(time.time()))
    signature = hashlib.sha256(
        (api_key + secret + timestamp).encode("utf-8")
    ).hexdigest()
    return {
        "Api-key": api_key,
        "X-Signature": signature,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    return os.environ.get("HOTELBEDS_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")


def _http_error_detail(response: httpx.Response) -> str:
    """Extract a short provider error without exposing request credentials."""
    try:
        detail = response.json().get("error", "")
    except ValueError:
        detail = response.text
    return str(detail).strip()[:200]


# ── Helpers ───────────────────────────────────────────────────────────────


# ── IATA City Code → Hotelbeds Destination Code mapping ──────────────────
# Hotelbeds uses its own destination codes which sometimes differ from IATA city
# codes. This maps known mismatches. If a code is not here, it's passed as-is.

_IATA_TO_HOTELBEDS: dict[str, str] = {
    # Europe — verified against Hotelbeds Content API destinations
    "ROM": "ROE",  # Rome (Hotelbeds ROM is La Romana, Dominican Republic)
    # Japan — Hotelbeds uses airport/region codes, not IATA city codes
    "TYO": "NRT",  # Tokyo (IATA city=TYO, Hotelbeds=NRT)
    "OSA": "ITM",  # Osaka (IATA city=OSA, Hotelbeds=ITM)
    "KYO": "KIX",  # Kyoto
    "SPK": "HKO",  # Sapporo → Hokkaido
    "NGO": "ACH",  # Nagoya → Aichi
    # South Korea
    "SEL": "ICN",  # Seoul (IATA city=SEL, Hotelbeds=ICN)
}


def _resolve_destination_code(iata_code: str) -> str:
    """Map an IATA city code to Hotelbeds destination code."""
    return _IATA_TO_HOTELBEDS.get(iata_code.upper(), iata_code.upper())


def _parse_star_rating(category_code: str) -> str:
    """Convert '3EST' → '★★★ (3 stars)'."""
    if category_code and category_code.endswith("EST"):
        num = category_code.replace("EST", "").strip()
        if num.isdigit():
            return f"{'★' * int(num)} ({num} stars)"
    return category_code or "N/A"


def _format_cancellation(policies: list[dict]) -> str:
    """Summarise cancellation policies into a readable line."""
    if not policies:
        return "No cancellation info"
    parts = []
    for pol in policies[:3]:
        amount = pol.get("amount", "?")
        from_date = pol.get("from", "?")
        if "T" in str(from_date):
            from_date = str(from_date).split("T")[0]
        parts.append(f"{amount} from {from_date}")
    return "; ".join(parts)


def _format_taxes(taxes_obj: dict | None) -> str:
    """Summarise tax information."""
    if not taxes_obj:
        return ""
    if taxes_obj.get("allIncluded"):
        return "All taxes included"
    tax_list = taxes_obj.get("taxes", [])
    if not tax_list:
        return ""
    parts = []
    for t in tax_list[:3]:
        included = "incl." if t.get("included") else "excl."
        amount = t.get("clientAmount") or t.get("amount") or t.get("percent", "")
        currency = t.get("clientCurrency") or t.get("currency", "")
        parts.append(f"{amount} {currency} ({included})")
    return "Taxes: " + ", ".join(parts)


def _build_occupancies(
    rooms: int,
    adults: int,
    children: int,
    children_ages: list[int] | None,
) -> list[dict]:
    """Build the occupancies payload, including child paxes when needed."""
    occ: dict = {"rooms": rooms, "adults": adults, "children": children}
    if children and children_ages:
        occ["paxes"] = [{"type": "CH", "age": age} for age in children_ages[:children]]
    return [occ]


# ── Availability API ──────────────────────────────────────────────────────


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception_type(httpx.RequestError),
)
async def _search_hotelbeds_api(
    check_in: str,
    check_out: str,
    adults: int,
    rooms: int = 1,
    children: int = 0,
    children_ages: list[int] | None = None,
    *,
    city_code: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius: int = 20,
    hotel_codes: list[int] | None = None,
    min_category: int | None = None,
    max_category: int | None = None,
    min_rate: float | None = None,
    max_rate: float | None = None,
    max_hotels: int = 50,
    max_rooms_per_hotel: int = 5,
    board_codes: list[str] | None = None,
    daily_rate: bool = True,
) -> list[dict]:
    """Search Hotelbeds availability with full filter support."""
    url = f"{_base_url()}/hotel-api/1.0/hotels"
    headers = _hotelbeds_headers()

    body: dict = {
        "stay": {"checkIn": check_in, "checkOut": check_out},
        "occupancies": _build_occupancies(rooms, adults, children, children_ages),
        "dailyRate": daily_rate,
    }

    # Location: destination code, geolocation, or specific hotel codes
    if hotel_codes:
        body["hotels"] = {"hotel": hotel_codes}
    elif latitude is not None and longitude is not None:
        body["geolocation"] = {
            "latitude": str(latitude),
            "longitude": str(longitude),
            "radius": min(radius, 200),
            "unit": "km",
        }
    elif city_code:
        body["destination"] = {"code": _resolve_destination_code(city_code)}
    else:
        raise ValueError("Provide city_code, lat/lng, or hotel_codes")

    # Filters
    api_filter: dict = {
        "maxHotels": min(max_hotels, 2000),
        "maxRooms": min(max_rooms_per_hotel, 50),
    }
    if min_category is not None:
        api_filter["minCategory"] = max(1, min(5, min_category))
    if max_category is not None:
        api_filter["maxCategory"] = max(1, min(5, max_category))
    if min_rate is not None:
        api_filter["minRate"] = max(0, min_rate)
    if max_rate is not None:
        api_filter["maxRate"] = max(0, max_rate)
    body["filter"] = api_filter

    if board_codes:
        body["boards"] = {"board": board_codes, "included": True}

    logger.debug(
        "Hotelbeds availability: %s %s→%s, %d adults, %d children",
        city_code or f"({latitude},{longitude})",
        check_in,
        check_out,
        adults,
        children,
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=body, timeout=20.0)
        resp.raise_for_status()

    data = resp.json()
    return data.get("hotels", {}).get("hotels", [])


# ── CheckRate API ─────────────────────────────────────────────────────────


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, max=8),
    retry=retry_if_exception_type(httpx.RequestError),
)
async def _check_rate_api(
    rate_keys: list[str],
    upselling: bool = False,
) -> dict:
    """Call Hotelbeds CheckRate for up-to-date pricing and optional upselling."""
    url = f"{_base_url()}/hotel-api/1.0/checkrates"
    headers = _hotelbeds_headers()
    body: dict = {
        "rooms": [{"rateKey": rk} for rk in rate_keys],
    }
    if upselling:
        body["upselling"] = True

    logger.debug(
        "Hotelbeds checkRate: %d rate keys, upselling=%s", len(rate_keys), upselling
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=body, timeout=30.0)
        resp.raise_for_status()

    return resp.json()


# ── Format a single hotel for text output ─────────────────────────────────


def _format_hotel(hotel: dict, index: int) -> str:
    """Format a hotel result into readable multi-line text."""
    name = hotel.get("name", "Unknown Hotel")
    cat_code = hotel.get("categoryCode", "")
    star_display = _parse_star_rating(cat_code)
    lat = hotel.get("latitude", "")
    lng = hotel.get("longitude", "")
    zone = hotel.get("zoneName", "")
    dest = hotel.get("destinationName", "")
    currency = hotel.get("currency", "USD")

    lines = [
        f"  {index}. {name}",
        f"     Category: {star_display}",
    ]
    if zone or dest:
        lines.append(f"     Location: {zone}{', ' + dest if dest else ''}")
    if lat and lng:
        lines.append(f"     Coordinates: {lat}, {lng}")

    rooms = hotel.get("rooms", [])
    for room in rooms[:2]:
        room_name = room.get("name", "Standard Room")
        rates = room.get("rates", [])
        if not rates:
            continue
        rate = rates[0]
        net = rate.get("net", "N/A")
        board = rate.get("boardName", rate.get("boardCode", "N/A"))
        rate_type = rate.get("rateType", "")
        rate_key = rate.get("rateKey", "")

        lines.append(f"     Room: {room_name}")
        lines.append(f"       Price: {net} {currency} (total stay)")
        lines.append(f"       Board: {board}")
        lines.append(f"       Rate type: {rate_type}")

        # Daily breakdown
        daily = rate.get("dailyRates", [])
        if daily:
            daily_strs = [
                f"night {d['offset'] + 1}: {d.get('dailyNet', '?')}" for d in daily[:7]
            ]
            lines.append(f"       Per night: {', '.join(daily_strs)}")

        # Cancellation policies
        cxl = rate.get("cancellationPolicies", [])
        if cxl:
            lines.append(f"       Cancellation: {_format_cancellation(cxl)}")

        # Promotions / offers
        promos = rate.get("promotions", [])
        if promos:
            promo_names = [p.get("name", p.get("code", "")) for p in promos[:3]]
            lines.append(f"       Promotions: {', '.join(promo_names)}")

        # Taxes
        taxes_str = _format_taxes(rate.get("taxes"))
        if taxes_str:
            lines.append(f"       {taxes_str}")

        if rate_key:
            lines.append(f"       Rate key: {rate_key}")

        if rate_type == "RECHECK":
            lines.append("       ⚠ Rate requires CheckRate verification before booking")

    return "\n".join(lines)


# ── Tools ─────────────────────────────────────────────────────────────────


@tool
async def search_hotels_hotelbeds(
    city_code: str,
    check_in_date: str,
    check_out_date: str,
    adults: int,
    children: int = 0,
    children_ages: str = "",
    min_category: int | None = None,
    max_rate: float | None = None,
    board_codes: str = "",
) -> str:
    """Search for hotels via Hotelbeds (250K+ hotels, strong on independents
    and boutique properties). Returns hotel name, category, price, room type,
    board type, cancellation policies, daily rates, and promotions.

    Hotelbeds prices are FINAL — net includes all supplements and discounts.

    Call lookup_iata_code first if you have a city name instead of a code.

    Args:
        city_code: IATA city code (e.g., "TYO" for Tokyo, "PAR" for Paris)
        check_in_date: Check-in date in YYYY-MM-DD format
        check_out_date: Check-out date in YYYY-MM-DD format
        adults: Number of adult guests (required — infer from the request, do not assume)
        children: Number of children (default 0)
        children_ages: Comma-separated ages of children (e.g., "4,8"). Required when children > 0
        min_category: Minimum star rating 1-5 (e.g., 3 for 3+ stars). Optional
        max_rate: Maximum total price filter. Optional
        board_codes: Comma-separated board type codes to filter. Optional.
            Common codes: RO=Room Only, BB=Bed&Breakfast, HB=Half Board,
            FB=Full Board, AI=All Inclusive
    """
    ages: list[int] = []
    if children_ages:
        ages = [int(a.strip()) for a in children_ages.split(",") if a.strip().isdigit()]

    parsed_boards = (
        [b.strip().upper() for b in board_codes.split(",") if b.strip()]
        if board_codes
        else None
    )

    try:
        hotels = await _search_hotelbeds_api(
            city_code=city_code.upper().strip(),
            check_in=check_in_date,
            check_out=check_out_date,
            adults=adults,
            children=children,
            children_ages=ages or None,
            min_category=min_category,
            max_rate=max_rate,
            board_codes=parsed_boards,
        )
    except httpx.HTTPStatusError as e:
        logger.error(
            "Hotelbeds HTTP error %s: %s",
            e.response.status_code,
            e.response.text[:300],
        )
        detail = _http_error_detail(e.response)
        suffix = f": {detail}" if detail else ""
        return f"Hotelbeds API error (HTTP {e.response.status_code}){suffix}."
    except httpx.RequestError as e:
        logger.error("Hotelbeds request error: %s", e)
        return f"Could not reach Hotelbeds API: {e}"
    except RuntimeError as e:
        return str(e)

    if not hotels:
        return (
            f"No hotel offers found on Hotelbeds in {city_code} "
            f"for {check_in_date} to {check_out_date}."
        )

    results = [
        f"Hotels from Hotelbeds in {city_code} "
        f"({check_in_date} to {check_out_date}, "
        f"{adults} adults{f', {children} children' if children else ''}):\n"
    ]

    for i, hotel in enumerate(hotels[:8], 1):
        results.append(_format_hotel(hotel, i))
        results.append("")

    # Flag if any rate requires CheckRate
    recheck_hotels = []
    for h in hotels[:8]:
        for room in h.get("rooms", []):
            for rate in room.get("rates", []):
                if rate.get("rateType") == "RECHECK":
                    recheck_hotels.append(h.get("name", "Unknown"))
                    break
            else:
                continue
            break
    if recheck_hotels:
        results.append(
            "⚠ Note: Hotels marked RECHECK require calling check_hotel_rate_hotelbeds "
            "with their rate key to get confirmed pricing before booking."
        )

    return "\n".join(results)


@tool
async def check_hotel_rate_hotelbeds(
    rate_keys: str,
    include_upselling: bool = False,
) -> str:
    """Verify the current price and get detailed rate breakdown for a Hotelbeds
    hotel room. MANDATORY for rates with rateType 'RECHECK' — those rates may
    have changed since the availability search.

    Also returns cancellation policy details and optional upselling (higher-
    category rooms at the same hotel).

    Args:
        rate_keys: One or more rate keys from the availability search,
            separated by '|||' if multiple.
            Example: "20260615|20260620|W|1|12345|DBL.ST|ID_B2B|RO|MRK1"
        include_upselling: If True, also returns higher-category room options
            at the same hotel (default False)
    """
    keys = [k.strip() for k in rate_keys.split("|||") if k.strip()]
    if not keys:
        return "No rate keys provided."

    try:
        data = await _check_rate_api(keys, upselling=include_upselling)
    except httpx.HTTPStatusError as e:
        logger.error(
            "Hotelbeds CheckRate HTTP error %s: %s",
            e.response.status_code,
            e.response.text[:300],
        )
        detail = _http_error_detail(e.response)
        suffix = f": {detail}" if detail else ""
        return f"Hotelbeds CheckRate error (HTTP {e.response.status_code}){suffix}."
    except httpx.RequestError as e:
        logger.error("Hotelbeds CheckRate request error: %s", e)
        return f"Could not reach Hotelbeds CheckRate API: {e}"
    except RuntimeError as e:
        return str(e)

    hotel = data.get("hotel") or data.get("hotels")
    if not hotel:
        return "CheckRate returned no hotel data — the rate may have expired."

    lines = ["Hotelbeds CheckRate results:\n"]

    name = hotel.get("name", "Hotel")
    lines.append(f"Hotel: {name}")
    lines.append(
        f"Check-in: {hotel.get('checkIn', '?')} → Check-out: {hotel.get('checkOut', '?')}"
    )
    lines.append(f"Total: {hotel.get('totalNet', '?')} {hotel.get('currency', '')}")

    mod = hotel.get("modificationPolicies", {})
    if mod:
        lines.append(
            f"Modifications: {'Yes' if mod.get('modification') else 'No'} | "
            f"Cancellation: {'Yes' if mod.get('cancellation') else 'No'}"
        )

    for room in hotel.get("rooms", []):
        lines.append(f"\n  Room: {room.get('name', room.get('code', '?'))}")
        for rate in room.get("rates", []):
            lines.append(
                f"    Net: {rate.get('net', '?')} | Board: {rate.get('boardName', rate.get('boardCode', '?'))}"
            )
            lines.append(f"    Rate key: {rate.get('rateKey', '?')}")

            cxl = rate.get("cancellationPolicies", [])
            if cxl:
                lines.append(f"    Cancellation: {_format_cancellation(cxl)}")

            breakdown = rate.get("rateBreakDown", {})
            discounts = breakdown.get("rateDiscounts", [])
            if discounts:
                disc_strs = [
                    f"{d.get('name', d.get('code', '?'))}: -{d.get('amount', '?')}"
                    for d in discounts
                ]
                lines.append(f"    Discounts: {', '.join(disc_strs)}")
            supplements = breakdown.get("rateSupplements", [])
            if supplements:
                supp_strs = [
                    f"{s.get('name', s.get('code', '?'))}: +{s.get('amount', '?')}"
                    for s in supplements
                ]
                lines.append(f"    Supplements: {', '.join(supp_strs)}")

            comments = rate.get("rateComments", "")
            if comments:
                lines.append(f"    Rate comments: {comments[:300]}")

    # Upselling options
    upselling = hotel.get("upselling", {})
    up_rooms = upselling.get("rooms", [])
    if up_rooms:
        lines.append("\n  Upselling options (higher-category rooms):")
        for up_room in up_rooms[:3]:
            for up_rate in up_room.get("rates", []):
                lines.append(
                    f"    {up_rate.get('boardName', '?')} — "
                    f"{up_rate.get('net', '?')} {hotel.get('currency', '')} | "
                    f"Rate key: {up_rate.get('rateKey', '?')}"
                )

    return "\n".join(lines)
