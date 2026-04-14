"""Google Maps Platform tools for Wanderlisted travel agent.

Enabled APIs (7):
  - Geocoding API          → _geocode() helper (address ↔ lat/lng)
  - Places API (New)       → search_places_nearby, search_places_text
  - Directions API         → get_directions
  - Distance Matrix API    → get_distance_matrix
  - Routes API             → compute_route, optimize_day_route
  - Time Zone API          → get_timezone
  - Maps Embed API         → used directly in handbook_template.html.j2 iframes

All calls go through a single API key read from GOOGLE_MAPS_API_KEY.
Each tool is stateless and safe to use inside any subagent.
"""

import os
import time
from typing import Optional
from urllib.parse import urlencode

import httpx

from langchain_core.tools import tool

from custom_logging import AppLogger

logger = AppLogger(logger_name="tools.google_maps", level="DEBUG")

_BASE_URL = "https://maps.googleapis.com/maps/api"
_ROUTES_URL = "https://routes.googleapis.com"

# ── helpers ──────────────────────────────────────────────────────────────


def _api_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY environment variable is not set")
    return key


def places_photo_url(photo_name: str, max_height: int = 400) -> str:
    """Convert a Places API (New) photo reference to a displayable image URL.

    Args:
        photo_name: Full photo resource name, e.g.
            ``places/ChIJ.../photos/AU_ZVE...``
        max_height: Maximum image height in pixels.

    Returns:
        URL string that serves the photo directly.
    """
    key = _api_key()
    return (
        f"https://places.googleapis.com/v1/{photo_name}/media"
        f"?maxHeightPx={max_height}&key={key}"
    )


def directions_embed_url(
    origin: str,
    destination: str,
    waypoints: list[str] | None = None,
    mode: str = "walking",
) -> str:
    """Build a Maps Embed API directions URL showing a route with blue line.

    Args:
        origin: Starting point (address or lat,lng).
        destination: End point.
        waypoints: Optional intermediate stops.
        mode: Travel mode — walking, driving, transit, bicycling.

    Returns:
        Embeddable iframe ``src`` URL.
    """
    key = _api_key()
    params: dict[str, str] = {
        "key": key,
        "origin": origin,
        "destination": destination,
        "mode": mode,
    }
    if waypoints:
        params["waypoints"] = "|".join(waypoints)
    return f"https://www.google.com/maps/embed/v1/directions?{urlencode(params)}"


def lookup_place_photo(place_name: str, city: str = "") -> str | None:
    """Quick Places text search to fetch the first photo URL for a place.

    Returns a displayable image URL or None if unavailable.
    This is a lightweight call requesting only displayName + photos.
    """
    key = _api_key()
    query = f"{place_name} {city}".strip()
    try:
        resp = httpx.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": "places.displayName,places.photos",
            },
            json={"textQuery": query, "maxResultCount": 1},
            timeout=10,
        )
        resp.raise_for_status()
        places = resp.json().get("places", [])
        if places:
            photos = places[0].get("photos", [])
            if photos:
                ref = photos[0].get("name", "")
                if ref:
                    return places_photo_url(ref)
    except Exception:
        pass
    return None


def _format_place(place: dict) -> str:
    """Format a single Places API (New) result into readable text."""
    name = place.get("name", place.get("displayName", {}).get("text", "Unknown"))
    if isinstance(name, dict):
        name = name.get("text", "Unknown")
    addr = place.get("formatted_address", place.get("formattedAddress", ""))
    rating = place.get("rating", "N/A")
    total_ratings = place.get("user_ratings_total", place.get("userRatingCount", 0))
    price = place.get("price_level", place.get("priceLevel", ""))
    price_str = {
        "PRICE_LEVEL_FREE": "Free",
        "PRICE_LEVEL_INEXPENSIVE": "$",
        "PRICE_LEVEL_MODERATE": "$$",
        "PRICE_LEVEL_EXPENSIVE": "$$$",
        "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
    }.get(str(price), str(price) if price else "N/A")
    status = place.get("business_status", place.get("businessStatus", ""))
    types = ", ".join(place.get("types", [])[:4])

    # Location coordinates
    loc = place.get("location", {})
    lat = loc.get("latitude", "")
    lng = loc.get("longitude", "")
    coords = f"{lat},{lng}" if lat and lng else ""

    # Google Maps link
    maps_uri = place.get("googleMapsUri", "")

    # Website
    website = place.get("websiteUri", "")

    # Editorial summary
    summary = place.get("editorialSummary", {})
    if isinstance(summary, dict):
        summary = summary.get("text", "")

    # Opening hours
    hours_obj = place.get("currentOpeningHours", place.get("regularOpeningHours", {}))
    hours_text = ""
    if isinstance(hours_obj, dict):
        weekday = hours_obj.get("weekdayDescriptions", [])
        if weekday:
            hours_text = weekday[0]  # Show first day as sample

    # Photo reference (first photo)
    photos = place.get("photos", [])
    photo_ref = ""
    if photos and isinstance(photos[0], dict):
        photo_ref = photos[0].get("name", "")

    # Build displayable photo URL from the reference
    photo_url = ""
    if photo_ref:
        try:
            photo_url = places_photo_url(photo_ref, max_height=400)
        except RuntimeError:
            pass

    lines = [
        f"• {name}",
        f"  Address: {addr}" if addr else None,
        f"  Coordinates: {coords}" if coords else None,
        f"  Rating: {rating}/5 ({total_ratings} reviews)" if rating != "N/A" else None,
        f"  Price: {price_str}" if price_str != "N/A" else None,
        f"  Summary: {summary}" if summary else None,
        f"  Hours: {hours_text}" if hours_text else None,
        f"  Status: {status}" if status else None,
        f"  Types: {types}" if types else None,
        f"  Google Maps: {maps_uri}" if maps_uri else None,
        f"  Website: {website}" if website else None,
        f"  Photo: {photo_url}" if photo_url else None,
    ]
    return "\n".join(line for line in lines if line)


# ── Places API (New) ────────────────────────────────────────────────────


@tool
def search_places_nearby(
    location: str,
    place_type: str,
    radius_meters: int = 1500,
    max_results: int = 10,
) -> str:
    """Search for places near a location using Google Places API.

    Args:
        location: Lat,lng string like "35.6762,139.6503" or a text description
                  (will be geocoded first).
        place_type: Google place type, e.g. "restaurant", "tourist_attraction",
                    "lodging", "cafe", "museum", "bar", "park".
        radius_meters: Search radius in metres (default 1500).
        max_results: Maximum number of results (default 10, max 20).
    """
    key = _api_key()

    # If location looks like text, geocode it first
    if not _looks_like_latlng(location):
        location = _geocode(location, key)
        if not location:
            return "Could not geocode the provided location."

    lat, lng = location.split(",")

    # Places API (New) — Nearby Search
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": (
            "places.displayName,places.formattedAddress,places.rating,"
            "places.userRatingCount,places.priceLevel,places.types,"
            "places.businessStatus,places.location,places.googleMapsUri,"
            "places.websiteUri,places.editorialSummary,places.photos,"
            "places.currentOpeningHours"
        ),
    }
    body = {
        "includedTypes": [place_type],
        "maxResultCount": min(max_results, 20),
        "locationRestriction": {
            "circle": {
                "center": {"latitude": float(lat), "longitude": float(lng)},
                "radius": float(radius_meters),
            }
        },
    }
    logger.debug(f"Places Nearby: type={place_type}, loc={location}")
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "Places Nearby HTTP error %s: %s",
            e.response.status_code,
            e.response.text[:200],
        )
        return (
            f"Places API error (HTTP {e.response.status_code}). Try a different search."
        )
    except httpx.RequestError as e:
        logger.error("Places Nearby request error: %s", e)
        return f"Could not reach Places API: {e}"
    data = resp.json()
    places = data.get("places", [])
    if not places:
        return f"No {place_type} found near {location}."
    return f"Found {len(places)} {place_type}(s):\n\n" + "\n\n".join(
        _format_place(p) for p in places
    )


@tool
def search_places_text(
    query: str,
    max_results: int = 10,
) -> str:
    """Search for places using a free-text query via Google Places API.

    Args:
        query: Natural language search, e.g. "best sushi in Shinjuku Tokyo",
               "budget hotels near Colosseum Rome".
        max_results: Maximum results (default 10, max 20).
    """
    key = _api_key()
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": (
            "places.displayName,places.formattedAddress,places.rating,"
            "places.userRatingCount,places.priceLevel,places.types,"
            "places.businessStatus,places.location,places.googleMapsUri,"
            "places.websiteUri,places.editorialSummary,places.photos,"
            "places.currentOpeningHours"
        ),
    }
    body = {"textQuery": query, "maxResultCount": min(max_results, 20)}
    logger.debug(f"Places Text Search: {query!r}")
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "Places Text HTTP error %s: %s",
            e.response.status_code,
            e.response.text[:200],
        )
        return (
            f"Places API error (HTTP {e.response.status_code}). Try a different query."
        )
    except httpx.RequestError as e:
        logger.error("Places Text request error: %s", e)
        return f"Could not reach Places API: {e}"
    data = resp.json()
    places = data.get("places", [])
    if not places:
        return f"No places found for: {query}"
    return f"Found {len(places)} result(s):\n\n" + "\n\n".join(
        _format_place(p) for p in places
    )


# ── Directions API ──────────────────────────────────────────────────────


@tool
def get_directions(
    origin: str,
    destination: str,
    mode: str = "transit",
    departure_time: Optional[str] = None,
) -> str:
    """Get directions between two points using Google Directions API.

    Args:
        origin: Start point — address or "lat,lng".
        destination: End point — address or "lat,lng".
        mode: Travel mode: "driving", "walking", "bicycling", "transit".
        departure_time: ISO datetime or "now" for transit (optional).
    """
    key = _api_key()
    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "key": key,
    }
    if departure_time:
        params["departure_time"] = departure_time

    url = f"{_BASE_URL}/directions/json?{urlencode(params)}"
    logger.debug(f"Directions: {origin} → {destination} ({mode})")
    try:
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "Directions HTTP error %s: %s",
            e.response.status_code,
            e.response.text[:200],
        )
        return f"Directions API error (HTTP {e.response.status_code})."
    except httpx.RequestError as e:
        logger.error("Directions request error: %s", e)
        return f"Could not reach Directions API: {e}"
    data = resp.json()

    if data.get("status") != "OK":
        return f"Directions API error: {data.get('status')} — {data.get('error_message', '')}"

    route = data["routes"][0]
    leg = route["legs"][0]
    steps_text = []
    for i, step in enumerate(leg["steps"][:15], 1):  # Cap at 15 steps
        instr = step.get("html_instructions", "").replace("<b>", "").replace("</b>", "")
        instr = instr.replace('<div style="font-size:0.9em">', " ").replace(
            "</div>", ""
        )
        dist = step["distance"]["text"]
        dur = step["duration"]["text"]
        transit_info = ""
        if "transit_details" in step:
            td = step["transit_details"]
            line = td.get("line", {})
            transit_info = f" [{line.get('vehicle', {}).get('type', '')} {line.get('short_name', line.get('name', ''))}]"
        steps_text.append(f"  {i}. {instr} ({dist}, {dur}){transit_info}")

    return (
        f"Route: {leg['start_address']} → {leg['end_address']}\n"
        f"Distance: {leg['distance']['text']}\n"
        f"Duration: {leg['duration']['text']}\n"
        f"Mode: {mode}\n\n"
        f"Steps:\n" + "\n".join(steps_text)
    )


# ── Distance Matrix API ─────────────────────────────────────────────────


@tool
def get_distance_matrix(
    origins: str,
    destinations: str,
    mode: str = "driving",
) -> str:
    """Get travel distances and durations between multiple origins and destinations.

    Args:
        origins: Pipe-separated origins, e.g. "Tokyo Station|Shinjuku Station".
        destinations: Pipe-separated destinations, e.g. "Senso-ji Temple|Tokyo Tower".
        mode: Travel mode: "driving", "walking", "bicycling", "transit".
    """
    key = _api_key()
    params = {
        "origins": origins,
        "destinations": destinations,
        "mode": mode,
        "key": key,
    }
    url = f"{_BASE_URL}/distancematrix/json?{urlencode(params)}"
    logger.debug(f"Distance Matrix: {origins} → {destinations} ({mode})")
    try:
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "Distance Matrix HTTP error %s: %s",
            e.response.status_code,
            e.response.text[:200],
        )
        return f"Distance Matrix API error (HTTP {e.response.status_code})."
    except httpx.RequestError as e:
        logger.error("Distance Matrix request error: %s", e)
        return f"Could not reach Distance Matrix API: {e}"
    data = resp.json()

    if data.get("status") != "OK":
        return f"Distance Matrix error: {data.get('status')}"

    origin_addrs = data.get("origin_addresses", [])
    dest_addrs = data.get("destination_addresses", [])
    rows = data.get("rows", [])

    lines = []
    for i, row in enumerate(rows):
        for j, elem in enumerate(row.get("elements", [])):
            status = elem.get("status", "UNKNOWN")
            if status == "OK":
                dist = elem["distance"]["text"]
                dur = elem["duration"]["text"]
                lines.append(f"• {origin_addrs[i]} → {dest_addrs[j]}: {dist}, {dur}")
            else:
                lines.append(f"• {origin_addrs[i]} → {dest_addrs[j]}: {status}")

    return f"Distance Matrix ({mode}):\n" + "\n".join(lines)


# ── Routes API (compute routes) ─────────────────────────────────────────


@tool
def compute_route(
    origin: str,
    destination: str,
    travel_mode: str = "DRIVE",
    waypoints: Optional[str] = None,
) -> str:
    """Compute an optimised route using Google Routes API.

    Args:
        origin: Start address or "lat,lng".
        destination: End address or "lat,lng".
        travel_mode: DRIVE, BICYCLE, WALK, TRANSIT, TWO_WHEELER.
        waypoints: Optional comma-separated intermediate stops.
    """
    key = _api_key()
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.legs,routes.optimizedIntermediateWaypointIndex",
    }

    def _make_waypoint(addr: str) -> dict:
        addr = addr.strip()
        if _looks_like_latlng(addr):
            lat, lng = addr.split(",")
            return {
                "location": {
                    "latLng": {"latitude": float(lat), "longitude": float(lng)}
                }
            }
        return {"address": addr}

    body: dict = {
        "origin": _make_waypoint(origin),
        "destination": _make_waypoint(destination),
        "travelMode": travel_mode,
    }
    if waypoints:
        body["intermediates"] = [_make_waypoint(w) for w in waypoints.split(",")]
        body["optimizeWaypointOrder"] = True

    logger.debug(f"Routes API: {origin} → {destination} via {waypoints or 'direct'}")
    try:
        resp = httpx.post(
            f"{_ROUTES_URL}/directions/v2:computeRoutes",
            headers=headers,
            json=body,
            timeout=20,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "Routes API HTTP error %s: %s",
            e.response.status_code,
            e.response.text[:200],
        )
        return f"Routes API error (HTTP {e.response.status_code})."
    except httpx.RequestError as e:
        logger.error("Routes API request error: %s", e)
        return f"Could not reach Routes API: {e}"
    data = resp.json()

    routes = data.get("routes", [])
    if not routes:
        return "No route found."

    route = routes[0]
    dist_km = route.get("distanceMeters", 0) / 1000
    duration = route.get("duration", "0s")

    result = f"Route: {origin} → {destination}\nDistance: {dist_km:.1f} km\nDuration: {duration}\nMode: {travel_mode}"

    opt_order = route.get("optimizedIntermediateWaypointIndex")
    if opt_order and waypoints:
        wp_list = [w.strip() for w in waypoints.split(",")]
        ordered = [wp_list[i] for i in opt_order]
        result += f"\nOptimised stop order: {' → '.join(ordered)}"

    return result


# ── Route Optimization API ──────────────────────────────────────────────


@tool
def optimize_day_route(
    stops: str,
    start_location: str,
    end_location: Optional[str] = None,
) -> str:
    """Optimize the order of stops for a day trip using Google Route Optimization.

    Takes a list of places to visit and returns the most efficient ordering.

    Args:
        stops: Comma-separated list of places to visit, e.g.
               "Senso-ji Temple, Tokyo Tower, Meiji Shrine, Tsukiji Market".
        start_location: Starting point (hotel address or "lat,lng").
        end_location: End point — defaults to start_location (round trip).
    """
    key = _api_key()
    if not end_location:
        end_location = start_location

    # Use Routes API with waypoint optimisation as a lightweight proxy
    # for the full Route Optimization API
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.optimizedIntermediateWaypointIndex,routes.legs.duration,routes.legs.distanceMeters",
    }

    def _make_wp(addr: str) -> dict:
        addr = addr.strip()
        if _looks_like_latlng(addr):
            lat, lng = addr.split(",")
            return {
                "location": {
                    "latLng": {"latitude": float(lat), "longitude": float(lng)}
                }
            }
        return {"address": addr}

    stop_list = [s.strip() for s in stops.split(",") if s.strip()]
    body = {
        "origin": _make_wp(start_location),
        "destination": _make_wp(end_location),
        "intermediates": [_make_wp(s) for s in stop_list],
        "travelMode": "DRIVE",
        "optimizeWaypointOrder": True,
    }

    logger.debug(f"Route Optimisation: {len(stop_list)} stops from {start_location}")
    try:
        resp = httpx.post(
            f"{_ROUTES_URL}/directions/v2:computeRoutes",
            headers=headers,
            json=body,
            timeout=25,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "Route Optimisation HTTP error %s: %s",
            e.response.status_code,
            e.response.text[:200],
        )
        return f"Route Optimisation API error (HTTP {e.response.status_code})."
    except httpx.RequestError as e:
        logger.error("Route Optimisation request error: %s", e)
        return f"Could not reach Route Optimisation API: {e}"
    data = resp.json()

    routes = data.get("routes", [])
    if not routes:
        return "Could not compute optimised route."

    route = routes[0]
    opt_order = route.get(
        "optimizedIntermediateWaypointIndex", list(range(len(stop_list)))
    )
    ordered = [stop_list[i] for i in opt_order]
    total_km = route.get("distanceMeters", 0) / 1000
    total_dur = route.get("duration", "0s")

    legs = route.get("legs", [])
    leg_details = []
    full_path = [start_location] + ordered + [end_location]
    for i, leg in enumerate(legs):
        leg_dist = leg.get("distanceMeters", 0) / 1000
        leg_dur = leg.get("duration", "?")
        leg_details.append(
            f"  {i + 1}. {full_path[i]} → {full_path[i + 1]}: {leg_dist:.1f} km, {leg_dur}"
        )

    return (
        f"Optimised day route ({len(stop_list)} stops):\n"
        f"Total distance: {total_km:.1f} km\n"
        f"Total duration: {total_dur}\n\n"
        f"Order:\n"
        f"  Start: {start_location}\n"
        + "\n".join(f"  → {s}" for s in ordered)
        + f"\n  → End: {end_location}\n\n"
        f"Leg details:\n" + "\n".join(leg_details)
    )


# ── Time Zone API ───────────────────────────────────────────────────────


@tool
def get_timezone(
    location: str,
    timestamp: Optional[int] = None,
) -> str:
    """Get timezone information for a location using Google Time Zone API.

    Args:
        location: Lat,lng string like "35.6762,139.6503" or a text address
                  (will be geocoded first).
        timestamp: Unix timestamp for the timezone query. Defaults to now.
                   Needed because timezone offset can vary with DST.
    """
    key = _api_key()

    if not _looks_like_latlng(location):
        location = _geocode(location, key)
        if not location:
            return "Could not geocode the provided location."

    if timestamp is None:
        timestamp = int(time.time())

    params = {
        "location": location,
        "timestamp": timestamp,
        "key": key,
    }
    url = f"{_BASE_URL}/timezone/json?{urlencode(params)}"
    logger.debug(f"TimeZone: {location} @ {timestamp}")
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "TimeZone HTTP error %s: %s", e.response.status_code, e.response.text[:200]
        )
        return f"Time Zone API error (HTTP {e.response.status_code})."
    except httpx.RequestError as e:
        logger.error("TimeZone request error: %s", e)
        return f"Could not reach Time Zone API: {e}"
    data = resp.json()

    if data.get("status") != "OK":
        return f"Time Zone API error: {data.get('status')} — {data.get('errorMessage', '')}"

    tz_id = data.get("timeZoneId", "Unknown")
    tz_name = data.get("timeZoneName", "Unknown")
    raw_offset = data.get("rawOffset", 0) / 3600
    dst_offset = data.get("dstOffset", 0) / 3600
    total_offset = raw_offset + dst_offset

    sign = "+" if total_offset >= 0 else ""
    return (
        f"Timezone: {tz_name} ({tz_id})\n"
        f"UTC offset: {sign}{total_offset:.1f}h (raw {sign}{raw_offset:.1f}h + DST {dst_offset:.1f}h)"
    )


# ── internal helpers ─────────────────────────────────────────────────────


def _looks_like_latlng(text: str) -> bool:
    parts = text.split(",")
    if len(parts) != 2:
        return False
    try:
        float(parts[0])
        float(parts[1])
        return True
    except ValueError:
        return False


def _geocode(address: str, key: str) -> str | None:
    """Geocode a text address to lat,lng string."""
    params = {"address": address, "key": key}
    url = f"{_BASE_URL}/geocode/json?{urlencode(params)}"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.error("Geocode error for %r: %s", address, e)
        return None
    data = resp.json()
    if data.get("status") == "OK" and data.get("results"):
        loc = data["results"][0]["geometry"]["location"]
        return f"{loc['lat']},{loc['lng']}"
    return None
