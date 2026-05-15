"""Quick script to test Hotelbeds API and see the raw + formatted output."""

import asyncio

from dotenv import load_dotenv

load_dotenv(override=True)

import os

os.environ["LANGCHAIN_TRACING_V2"] = "false"

from src.tools.hotels_hotelbeds import _search_hotelbeds_api, search_hotels_hotelbeds


async def main():
    raw = await _search_hotelbeds_api("PAR", "2026-09-15", "2026-09-18", 1)
    print(f"Total hotels returned: {len(raw)}")
    print()

    for i, h in enumerate(raw[:3], 1):
        rooms = h.get("rooms", [])
        best_rate = rooms[0]["rates"][0] if rooms and rooms[0].get("rates") else {}
        print(f"{i}. {h.get('name', '?')}")
        print(f"   Code: {h.get('code')}")
        print(f"   Category: {h.get('categoryCode')} / {h.get('categoryName')}")
        print(
            f"   Destination: {h.get('destinationCode')} / {h.get('destinationName')}"
        )
        print(f"   Lat/Lng: {h.get('latitude')}, {h.get('longitude')}")
        print(f"   Room types: {len(rooms)}")
        if best_rate:
            print(
                f"   Best rate: ${best_rate.get('net')} {best_rate.get('currency', 'USD')}"
            )
            print(
                f"   Board: {best_rate.get('boardName')} ({best_rate.get('boardCode')})"
            )
            print(f"   Rate type: {best_rate.get('rateType')}")
            cp = best_rate.get("cancellationPolicies", [])
            if cp:
                print(f"   Cancel: ${cp[0].get('amount')} from {cp[0].get('from')}")
            taxes = best_rate.get("taxes", {}).get("taxes", [])
            if taxes:
                print(
                    f"   Tax: {taxes[0].get('amount')} {taxes[0].get('currency')} ({taxes[0].get('subType')})"
                )
        print()

    print("=" * 60)
    print("FORMATTED TOOL OUTPUT (what the agent sees):")
    print("=" * 60)
    result = await search_hotels_hotelbeds.ainvoke(
        {
            "city_code": "PAR",
            "check_in_date": "2026-09-15",
            "check_out_date": "2026-09-18",
            "adults": 1,
        }
    )
    print(result)


asyncio.run(main())
