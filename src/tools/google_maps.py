"""Google Maps Platform tools for Wanderlisted travel agent.

Enabled APIs (4):
  - Geocoding API          → _geocode() helper (address ↔ lat/lng)
  - Places API (New)       → search_places_nearby, search_places_text
  - Routes API             → compute_route, optimize_day_route
  - Maps Embed API         → used directly in handbook_template.html.j2 iframes

Routing is consolidated on the modern Routes API: ``compute_route`` handles
point-to-point directions (with turn-by-turn / transit steps) and multi-stop
routes, while ``optimize_day_route`` reorders a day's stops. The legacy
Directions and Distance Matrix APIs are no longer used.

All calls go through a single API key read from GOOGLE_MAPS_API_KEY.
Each tool is stateless and safe to use inside any subagent.
"""

import os
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
        place_type: One Google place type identifier in lowercase snake_case,
                e.g. "restaurant", "sushi_restaurant", "seafood_restaurant",
                "tourist_attraction", "cafe", "museum", "bar". Free-text
                phrases such as "seafood restaurant" are invalid; use
                search_places_text for those.
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


# ── Routes API (compute routes) ─────────────────────────────────────────


@tool
def compute_route(
    origin: str,
    destination: str,
    travel_mode: str = "DRIVE",
    waypoints: list[str] | None = None,
    include_steps: bool = True,
) -> str:
    """Compute a route with the Google Routes API.

    The single routing tool for Wanderlisted. Handles simple A→B directions,
    transit routing with line details, and multi-stop routes with automatic
    waypoint optimisation. Replaces the legacy Directions and Distance Matrix
    APIs. The result contains route endpoints, distance, duration, selected mode,
    optional optimized stop order, and available steps. It does not contain
    fares or pass validity, schedules or frequency, accessibility guarantees,
    reservations, luggage rules, parking, reliability, or traffic forecasts.

    Preserve an explicitly requested travel mode and endpoints. Do not probe a
    different mode or substitute endpoint unless the user explicitly requests
    that comparison. A non-transit multi-stop trip is one call with all requested
    waypoints; do not also issue calls for each leg. TRANSIT is point-to-point, so
    an explicitly multi-stop transit trip requires one call per consecutive leg.

    Args:
        origin: Start address or "lat,lng".
        destination: End address or "lat,lng".
        travel_mode: DRIVE, BICYCLE, WALK, TRANSIT, TWO_WHEELER.
        waypoints: Optional intermediate stops. Rejected for TRANSIT, which
            requires separate consecutive point-to-point calls.
        include_steps: Include turn-by-turn / transit step details (default True).
    """
    travel_mode = travel_mode.upper()
    is_transit = travel_mode == "TRANSIT"
    if is_transit and waypoints:
        return (
            "TRANSIT does not support waypoints. Call compute_route once per "
            "consecutive requested leg without waypoints."
        )
    key = _api_key()

    field_mask = [
        "routes.duration",
        "routes.distanceMeters",
        "routes.legs.duration",
        "routes.legs.distanceMeters",
        "routes.optimizedIntermediateWaypointIndex",
    ]
    if include_steps:
        field_mask += [
            "routes.legs.steps.distanceMeters",
            "routes.legs.steps.staticDuration",
            "routes.legs.steps.navigationInstruction",
            "routes.legs.steps.travelMode",
            "routes.legs.steps.transitDetails",
        ]

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": ",".join(field_mask),
    }

    body: dict = {
        "origin": _make_route_waypoint(origin),
        "destination": _make_route_waypoint(destination),
        "travelMode": travel_mode,
    }
    # TRANSIT is point-to-point only; waypoint optimisation applies to other modes.
    if waypoints and not is_transit:
        body["intermediates"] = [_make_route_waypoint(w) for w in waypoints]
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
    if opt_order is not None and waypoints and not is_transit:
        ordered = [waypoints[i] for i in opt_order]
        result += f"\nOptimised stop order: {' → '.join(ordered)}"

    if include_steps:
        steps = _format_route_steps(route)
        if steps:
            result += "\n\nSteps:\n" + steps

    return result


# ── Route Optimization API ──────────────────────────────────────────────


def compute_day_route_data(
    stops: list[str],
    start_location: str,
    end_location: str = "",
    travel_mode: str = "DRIVE",
) -> dict:
    """Compute structured route data for selected stops.

    Non-transit routes use waypoint optimization in one request. Public-transit
    routes preserve the selected order and compute each leg independently because
    Google Routes does not support transit waypoint optimization.
    """
    key = _api_key()
    end_location = end_location or start_location
    stop_list = [stop.strip() for stop in stops if stop.strip()]
    mode = _google_route_mode(travel_mode)

    if not stop_list:
        return {
            "ordered_stops": [],
            "legs": [],
            "total_distance_meters": 0,
            "total_duration_seconds": 0,
            "error": "No stops provided.",
        }

    if mode == "TRANSIT":
        full_path = [start_location, *stop_list, end_location]
        legs: list[dict] = []
        errors: list[str] = []
        for origin, destination in zip(full_path, full_path[1:]):
            response = _request_routes(
                key=key,
                origin=origin,
                destination=destination,
                travel_mode=mode,
                include_steps=True,
            )
            if response.get("error"):
                errors.append(f"{origin} → {destination}: {response['error']}")
                continue
            route = response["route"]
            leg = route.get("legs", [{}])[0]
            instructions = _format_route_steps({"legs": [leg]}).splitlines()
            legs.append(
                {
                    "from_location": origin,
                    "to_location": destination,
                    "distance_meters": int(leg.get("distanceMeters", 0)),
                    "duration_seconds": _duration_seconds(leg.get("duration", "0s")),
                    "instructions": instructions,
                }
            )
        return {
            "ordered_stops": stop_list,
            "legs": legs,
            "total_distance_meters": sum(leg["distance_meters"] for leg in legs),
            "total_duration_seconds": sum(leg["duration_seconds"] for leg in legs),
            "error": "; ".join(errors),
        }

    response = _request_routes(
        key=key,
        origin=start_location,
        destination=end_location,
        travel_mode=mode,
        intermediates=stop_list,
        optimize_waypoints=True,
        include_steps=False,
    )
    if response.get("error"):
        return {
            "ordered_stops": stop_list,
            "legs": [],
            "total_distance_meters": 0,
            "total_duration_seconds": 0,
            "error": response["error"],
        }

    route = response["route"]
    order = route.get("optimizedIntermediateWaypointIndex")
    expected_indices = list(range(len(stop_list)))
    if not isinstance(order, list) or sorted(order) != expected_indices:
        order = list(range(len(stop_list)))
    ordered = [stop_list[index] for index in order]
    full_path = [start_location, *ordered, end_location]
    legs = []
    for index, leg in enumerate(route.get("legs", [])[: len(full_path) - 1]):
        legs.append(
            {
                "from_location": full_path[index],
                "to_location": full_path[index + 1],
                "distance_meters": int(leg.get("distanceMeters", 0)),
                "duration_seconds": _duration_seconds(leg.get("duration", "0s")),
                "instructions": [],
            }
        )
    return {
        "ordered_stops": ordered,
        "legs": legs,
        "total_distance_meters": int(route.get("distanceMeters", 0)),
        "total_duration_seconds": _duration_seconds(route.get("duration", "0s")),
        "error": "",
    }


@tool
def optimize_day_route(
    stops: list[str],
    start_location: str,
    end_location: str = "",
    travel_mode: str = "DRIVE",
) -> str:
    """Optimize or plan the route for a selected list of day-trip stops.

    Takes a list of places to visit and returns the most efficient ordering.

    Args:
        stops: Places to visit, e.g. ["Senso-ji Temple", "Tokyo Tower"].
        start_location: Starting point (hotel address or "lat,lng").
        end_location: End point — defaults to start_location (round trip).
        travel_mode: DRIVE, WALK, BICYCLE, TRANSIT, TWO_WHEELER.
    """
    route = compute_day_route_data(
        stops=stops,
        start_location=start_location,
        end_location=end_location,
        travel_mode=travel_mode,
    )
    if route["error"] and not route["legs"]:
        return f"Could not compute optimised route: {route['error']}"

    ordered = route["ordered_stops"]
    total_km = route["total_distance_meters"] / 1000
    total_dur = f"{route['total_duration_seconds']}s"
    final_location = end_location or start_location
    leg_details = [
        (
            f"  {index}. {leg['from_location']} → {leg['to_location']}: "
            f"{leg['distance_meters'] / 1000:.1f} km, {leg['duration_seconds']}s"
        )
        for index, leg in enumerate(route["legs"], 1)
    ]

    return (
        f"Optimised day route ({len(stops)} stops, mode={_google_route_mode(travel_mode)}):\n"
        f"Total distance: {total_km:.1f} km\n"
        f"Total duration: {total_dur}\n\n"
        f"Order:\n"
        f"  Start: {start_location}\n"
        + "\n".join(f"  → {s}" for s in ordered)
        + f"\n  → End: {final_location}\n\n"
        f"Leg details:\n"
        + "\n".join(leg_details)
        + (f"\n\nWarnings: {route['error']}" if route["error"] else "")
    )


# ── internal helpers ─────────────────────────────────────────────────────


def _make_route_waypoint(address: str) -> dict:
    address = address.strip()
    if _looks_like_latlng(address):
        latitude, longitude = address.split(",")
        return {
            "location": {
                "latLng": {
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                }
            }
        }
    return {"address": address}


def _google_route_mode(travel_mode: str) -> str:
    mode = travel_mode.strip().upper()
    if mode in {"TRAIN", "BUS", "FERRY", "SUBWAY"}:
        return "TRANSIT"
    if mode not in {"DRIVE", "WALK", "BICYCLE", "TRANSIT", "TWO_WHEELER"}:
        return "TRANSIT"
    return mode


def _duration_seconds(duration: str) -> int:
    try:
        return max(0, int(float(duration.removesuffix("s"))))
    except (AttributeError, TypeError, ValueError):
        return 0


def _request_routes(
    *,
    key: str,
    origin: str,
    destination: str,
    travel_mode: str,
    intermediates: list[str] | None = None,
    optimize_waypoints: bool = False,
    include_steps: bool = False,
) -> dict:
    field_mask = [
        "routes.duration",
        "routes.distanceMeters",
        "routes.legs.duration",
        "routes.legs.distanceMeters",
        "routes.optimizedIntermediateWaypointIndex",
    ]
    if include_steps:
        field_mask.extend(
            [
                "routes.legs.steps.distanceMeters",
                "routes.legs.steps.staticDuration",
                "routes.legs.steps.navigationInstruction",
                "routes.legs.steps.travelMode",
                "routes.legs.steps.transitDetails",
            ]
        )
    body: dict = {
        "origin": _make_route_waypoint(origin),
        "destination": _make_route_waypoint(destination),
        "travelMode": travel_mode,
    }
    if intermediates:
        body["intermediates"] = [
            _make_route_waypoint(location) for location in intermediates
        ]
        body["optimizeWaypointOrder"] = optimize_waypoints
    try:
        response = httpx.post(
            f"{_ROUTES_URL}/directions/v2:computeRoutes",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": ",".join(field_mask),
            },
            json=body,
            timeout=25,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Routes API HTTP error %s: %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return {"error": f"Routes API error (HTTP {exc.response.status_code})."}
    except httpx.RequestError as exc:
        logger.error("Routes API request error: %s", exc)
        return {"error": f"Could not reach Routes API: {exc}"}
    routes = response.json().get("routes", [])
    if not routes:
        return {"error": "No route found."}
    return {"route": routes[0], "error": ""}


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


def _format_route_steps(route: dict) -> str:
    """Format up to 15 turn-by-turn / transit steps from a Routes API route."""
    lines: list[str] = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            if len(lines) >= 15:  # Cap at 15 steps
                return "\n".join(lines)
            dist_m = step.get("distanceMeters", 0)
            dist_str = f"{dist_m / 1000:.1f} km" if dist_m >= 1000 else f"{dist_m} m"
            dur = step.get("staticDuration", "")
            transit = step.get("transitDetails")
            if transit:
                line = transit.get("transitLine", {})
                name = line.get("nameShort") or line.get("name", "")
                vehicle = line.get("vehicle", {}).get("type", "")
                stop_details = transit.get("stopDetails", {})
                dep = stop_details.get("departureStop", {}).get("name", "")
                arr = stop_details.get("arrivalStop", {}).get("name", "")
                count = transit.get("stopCount", "")
                detail = f"[{vehicle} {name}]".strip()
                segment = f"{dep} → {arr}" if dep or arr else ""
                extra = f" ({count} stops)" if count else ""
                dur_str = f" [{dur}]" if dur else ""
                lines.append(
                    f"  {len(lines) + 1}. {detail} {segment}{extra}{dur_str}".rstrip()
                )
            else:
                instr = step.get("navigationInstruction", {}).get("instructions", "")
                instr = instr.replace("\n", " ").strip()
                if not instr:
                    continue
                dur_str = f", {dur}" if dur else ""
                lines.append(f"  {len(lines) + 1}. {instr} ({dist_str}{dur_str})")
    return "\n".join(lines)


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
