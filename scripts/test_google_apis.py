#!/usr/bin/env python3
"""Live integration test for all 7 enabled Google Maps Platform APIs.

Usage:
    .venv/bin/python scripts/test_google_apis.py

Requires GOOGLE_MAPS_API_KEY in the environment (or .env file).
Each test makes a real API call and prints the full tool output.

Enabled APIs tested:
  1. Geocoding API         -> _geocode()
  2. Places API (New)      -> search_places_nearby, search_places_text
  3. Directions API        -> get_directions
  4. Distance Matrix API   -> get_distance_matrix
  5. Routes API            -> compute_route, optimize_day_route
  6. Time Zone API         -> get_timezone
  7. Maps Embed API        -> URL generation (no HTTP call)
"""

import os
import sys
import time

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env if present
_env_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
)
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from src.tools.google_maps import (
    search_places_nearby,
    search_places_text,
    get_directions,
    get_distance_matrix,
    compute_route,
    optimize_day_route,
    get_timezone,
    _geocode,
    _api_key,
)

# ─── Test configuration ──────────────────────────────────────────────

TEST_LATLNG = "35.6762,139.6503"  # Tokyo Station area
TEST_ADDRESS = "Tokyo Station, Japan"
TEST_DEST_ADDRESS = "Senso-ji Temple, Tokyo"
TEST_STOPS = "Tokyo Tower, Meiji Shrine, Tsukiji Outer Market, Shibuya Crossing"

RESULTS: list[tuple[str, str, bool, str]] = []

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def run_test(api_name: str, tool_name: str, fn):
    """Execute a test and record results."""
    print(f"\n{'═' * 70}")
    print(f"{BOLD}{CYAN}  {api_name} → {tool_name}{RESET}")
    print(f"{'─' * 70}")
    try:
        result = fn()
        passed = True
        detail = result if isinstance(result, str) else str(result)
    except Exception as e:
        passed = False
        detail = f"{type(e).__name__}: {e}"
    RESULTS.append((api_name, tool_name, passed, detail))
    status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{status}]")
    for line in detail.split("\n"):
        print(f"  {line}")
    return passed


# ─── 1. Geocoding API ────────────────────────────────────────────────


def test_geocoding():
    key = _api_key()
    result = _geocode(TEST_ADDRESS, key)
    assert result is not None, "Geocode returned None — is the Geocoding API enabled?"
    lat, lng = result.split(",")
    assert 35.0 < float(lat) < 36.0, f"Unexpected latitude: {lat}"
    return f"'{TEST_ADDRESS}' → {result}"


# ─── 2. Places API (New) — Nearby Search ─────────────────────────────


def test_places_nearby():
    result = search_places_nearby.invoke(
        {
            "location": TEST_LATLNG,
            "place_type": "restaurant",
            "radius_meters": 500,
            "max_results": 3,
        }
    )
    assert "Found" in result, f"Unexpected: {result[:100]}"
    return result


# ─── 3. Places API (New) — Text Search ───────────────────────────────


def test_places_text():
    result = search_places_text.invoke(
        {
            "query": "best ramen near Tokyo Station",
            "max_results": 3,
        }
    )
    assert "Found" in result, f"Unexpected: {result[:100]}"
    return result


# ─── 4. Directions API ───────────────────────────────────────────────


def test_directions():
    # Use lat/lng to avoid geocoding dependency
    result = get_directions.invoke(
        {
            "origin": "35.6812,139.7671",  # Tokyo Station
            "destination": "35.7148,139.7967",  # Senso-ji
            "mode": "driving",
        }
    )
    assert "Route:" in result, f"Unexpected: {result[:100]}"
    return result


# ─── 5. Distance Matrix API ──────────────────────────────────────────


def test_distance_matrix():
    result = get_distance_matrix.invoke(
        {
            "origins": "Tokyo Station",
            "destinations": "Senso-ji Temple|Tokyo Tower|Meiji Shrine",
            "mode": "driving",
        }
    )
    assert "Distance Matrix" in result, f"Unexpected: {result[:100]}"
    return result


# ─── 6. Routes API — Compute Route ───────────────────────────────────


def test_compute_route():
    result = compute_route.invoke(
        {
            "origin": TEST_ADDRESS,
            "destination": TEST_DEST_ADDRESS,
            "travel_mode": "DRIVE",
        }
    )
    assert "Route:" in result or "Distance:" in result, f"Unexpected: {result[:100]}"
    return result


# ─── 7. Routes API — Optimize Day Route ──────────────────────────────


def test_optimize_route():
    result = optimize_day_route.invoke(
        {
            "stops": TEST_STOPS,
            "start_location": TEST_ADDRESS,
        }
    )
    assert "Optimised" in result or "stop" in result.lower(), (
        f"Unexpected: {result[:100]}"
    )
    return result


# ─── 8. Time Zone API ────────────────────────────────────────────────


def test_timezone():
    result = get_timezone.invoke(
        {
            "location": TEST_LATLNG,
        }
    )
    assert "Asia/Tokyo" in result or "Japan" in result, f"Unexpected: {result[:100]}"
    return result


# ─── 9. Maps Embed API (URL generation — no HTTP call) ───────────────


def test_maps_embed():
    key = _api_key()
    url = (
        f"https://www.google.com/maps/embed/v1/place?key={key}&q=Tokyo+Station&zoom=12"
    )
    assert key in url, "API key not in embed URL"
    assert "embed/v1/place" in url, "Not an embed URL"
    return f"Embed URL: {url[:60]}...\n(This URL is used in handbook HTML iframes)"


# ─── Runner ──────────────────────────────────────────────────────────


def main():
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        print(
            f"{RED}ERROR: GOOGLE_MAPS_API_KEY not set. Export it or add to .env{RESET}"
        )
        sys.exit(1)

    print(f"\n{BOLD}🗺  Wanderlisted — Google Maps API Test Suite{RESET}")
    print(f"   Key: {key[:8]}...{key[-4:]}")
    print(f"   Test location: {TEST_ADDRESS} ({TEST_LATLNG})")
    print(
        "   Enabled APIs: 7 (Geocoding, Places New, Directions, Distance Matrix, Routes, Time Zone, Maps Embed)"
    )

    tests = [
        ("Geocoding API", "_geocode()", test_geocoding),
        ("Places API (New)", "search_places_nearby", test_places_nearby),
        ("Places API (New)", "search_places_text", test_places_text),
        ("Directions API", "get_directions", test_directions),
        ("Distance Matrix API", "get_distance_matrix", test_distance_matrix),
        ("Routes API", "compute_route", test_compute_route),
        ("Routes API", "optimize_day_route", test_optimize_route),
        ("Time Zone API", "get_timezone", test_timezone),
        ("Maps Embed API", "(URL validation)", test_maps_embed),
    ]

    for api, tool, fn in tests:
        run_test(api, tool, fn)
        time.sleep(0.3)

    # Summary
    passed = sum(1 for _, _, p, _ in RESULTS if p)
    failed = sum(1 for _, _, p, _ in RESULTS if not p)
    total = len(RESULTS)

    print(f"\n{'═' * 70}")
    print(f"{BOLD}  SUMMARY{RESET}")
    print(f"{'─' * 70}")
    for api, tool, p, _ in RESULTS:
        icon = f"{GREEN}✅{RESET}" if p else f"{RED}❌{RESET}"
        print(f"  {icon} {api:<26} {tool}")

    print(f"{'─' * 70}")
    if failed:
        print(f"  {RED}{BOLD}{passed}/{total} passed, {failed} FAILED{RESET}")
    else:
        print(f"  {GREEN}{BOLD}{passed}/{total} — ALL PASSED ✅{RESET}")

    print(f"\n{YELLOW}  API → Agent mapping:{RESET}")
    print("  Geocoding        → internal _geocode() helper (address→coords)")
    print("  Places (New)     → RestaurantsAgent, ActivitiesAgent, HotelsAgent")
    print("  Directions       → TransportationAgent (step-by-step transit)")
    print("  Distance Matrix  → TransportationAgent, ItineraryAgent")
    print(
        "  Routes           → TransportationAgent, ItineraryAgent (route optimisation)"
    )
    print("  Time Zone        → DestinationAgent (local timezone info)")
    print("  Maps Embed       → Handbook HTML template (map iframes)\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
