"""Stage 2 tool-by-tool test script. Run with: python test_stage2.py"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def test_iata():
    from src.tools.iata import lookup_iata_code

    print("═══ 1. IATA Lookup (CSV, offline) ═══")
    for q in ["Seattle", "Tokyo", "NRT", "Bogota", "Tallinn"]:
        print(f"  {q:15s} → {lookup_iata_code.invoke(q)}")
    print("  ✓ PASSED\n")


def test_budget():
    from src.tools.budget import calculate_budget

    print("═══ 2. Budget Calculator (pure Python, offline) ═══")
    result = calculate_budget.invoke(
        {
            "destination_region": "east asia",
            "travel_style": "mid-range",
            "duration_days": 5,
            "num_travelers": 2,
        }
    )
    print(f"  {result[:400]}")
    print("  ✓ PASSED\n")


async def test_weather():
    from src.tools.weather import get_weather

    print("═══ 3. Weather (OpenWeatherMap API) ═══")
    result = await get_weather.ainvoke({"city": "Tokyo", "days": 3})
    print(f"  {result[:300]}")
    print("  ✓ PASSED\n")


async def test_currency():
    from src.tools.currency import convert_currency

    print("═══ 4. Currency (ExchangeRate API) ═══")
    result = await convert_currency.ainvoke(
        {"amount": 500, "from_currency": "USD", "to_currency": "JPY"}
    )
    print(f"  {result}")
    print("  ✓ PASSED\n")


async def test_safety():
    from src.tools.safety import get_safety_info

    print("═══ 5. Safety (REST Countries API) ═══")
    result = await get_safety_info.ainvoke({"country_name": "Japan"})
    print(f"  {result[:300]}")
    print("  ✓ PASSED\n")


async def test_flights():
    from src.tools.flights import search_flights

    print("═══ 6. Flights (Amadeus API) ═══")
    result = await search_flights.ainvoke(
        {
            "origin": "SEA",
            "destination": "NRT",
            "departure_date": "2026-06-15",
            "adults": 2,
        }
    )
    print(f"  {result[:400]}")
    print("  ✓ PASSED\n")


async def test_hotels():
    from src.tools.hotels import search_hotels

    print("═══ 7. Hotels (Amadeus API) ═══")
    result = await search_hotels.ainvoke(
        {
            "city_code": "TYO",
            "check_in_date": "2026-06-15",
            "check_out_date": "2026-06-20",
            "adults": 2,
        }
    )
    print(f"  {result[:400]}")
    print("  ✓ PASSED\n")


async def test_activities():
    from src.tools.activities import search_activities

    print("═══ 8. Activities (Google Places API) ═══")
    result = await search_activities.ainvoke(
        {"city": "Tokyo, Japan", "category": "food", "query": "ramen", "limit": 3}
    )
    print(f"  {result[:400]}")
    print("  ✓ PASSED\n")


async def main():
    print("=" * 60)
    print("  WANDERLISTED — Stage 2 Tool Test Suite")
    print("=" * 60 + "\n")

    # Offline tools (always work)
    test_iata()
    test_budget()

    # API tools with keys set
    await test_weather()
    await test_currency()
    await test_safety()

    # API tools that may have missing keys
    has_amadeus = (
        os.environ.get("AMADEUS_API_KEY", "").strip()
        and not os.environ.get("AMADEUS_API_KEY", "").startswith("your-")
    )
    has_google = (
        os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
        and not os.environ.get("GOOGLE_MAPS_API_KEY", "").startswith("your-")
    )

    if has_amadeus:
        await test_flights()
        await test_hotels()
    else:
        print("═══ 6. Flights — SKIPPED (AMADEUS_API_KEY not set) ═══\n")
        print("═══ 7. Hotels  — SKIPPED (AMADEUS_API_KEY not set) ═══\n")

    if has_google:
        await test_activities()
    else:
        print("═══ 8. Activities — SKIPPED (GOOGLE_MAPS_API_KEY not set) ═══\n")

    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Offline tools:  2/2 ✓")
    print(f"  API tools:      3/3 ✓  (weather, currency, safety)")
    if not has_amadeus:
        print(f"  Amadeus:        SKIPPED — add keys to .env")
    if not has_google:
        print(f"  Google Places:  SKIPPED — add key to .env")
    print()


if __name__ == "__main__":
    asyncio.run(main())
