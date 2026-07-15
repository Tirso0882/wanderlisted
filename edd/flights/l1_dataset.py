"""Golden dataset for the FLIGHTS agent — component level (one dataset per agent).

Each item is a `(query, expected)` pair. `expected` is the GROUND TRUTH for that
query — your definition of a correct decision, written from the task, never from
the agent's output.

Conventions:
  - Airports use a SET of every valid answer: any of a city's airports OR its
    metro code (New York -> {JFK, EWR, LGA, NYC}).
  - Omit a field the query didn't specify (e.g. no cabin) -> that check SKIPs.

This is the Flights slice of the pyramid's bottom layer. Integration and
end-to-end datasets (whole-trip requests) live separately, at their own levels.
"""

from __future__ import annotations

DATASET: list[dict] = [
    {
        "query": "Find flights from Amsterdam to Lisbon on 2026-09-10, 1 adult, economy.",
        "expected": {
            "origin": "AMS",
            "destination": "LIS",
            "departure_date": "2026-09-10",
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Flights from Dublin to Barcelona departing 2026-09-12 for 2 adults, economy.",
        "expected": {
            "origin": "DUB",
            "destination": "BCN",
            "departure_date": "2026-09-12",
            "adults": 2,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "I need a flight from Madrid to Copenhagen on 2026-09-15, one adult.",
        # No cabin in the query -> correct_cabin SKIPs this case (score None).
        "expected": {
            "origin": "MAD",
            "destination": "CPH",
            "departure_date": "2026-09-15",
            "adults": 1,
        },
    },
    {
        "query": "Book economy flights from Zurich to Vienna, 2026-09-18, 1 passenger.",
        "expected": {
            "origin": "ZRH",
            "destination": "VIE",
            "departure_date": "2026-09-18",
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Flights from New York to Tokyo on 2026-09-10, 1 adult, economy.",
        # Ground truth for a city = ANY of its airports OR its metro code.
        # New York: JFK/EWR/LGA + metro NYC. Tokyo: NRT/HND + metro TYO.
        "expected": {
            "origin": {"JFK", "EWR", "LGA", "NYC"},
            "destination": {"NRT", "HND", "TYO"},
            "departure_date": "2026-09-10",
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    # ── agent-stressing cases: exercise return_date, child/infant counts,
    #    premium cabins, and multi-airport cities (each field maps to an existing
    #    L1 evaluator). Airports use SETS = any valid airport OR the metro code. ──
    {
        "query": "Round-trip from Berlin to Rome, departing 2026-10-05, returning 2026-10-12, 1 adult, economy.",
        "expected": {
            "origin": "BER",
            "destination": {"FCO", "CIA", "ROM"},
            "departure_date": "2026-10-05",
            "return_date": "2026-10-12",  # tests round-trip: the return leg
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Flights from Manchester to Malaga on 2026-08-20 for 2 adults, 2 children and 1 infant, economy.",
        "expected": {
            "origin": "MAN",
            "destination": "AGP",
            "departure_date": "2026-08-20",
            "adults": 2,
            "children": 2,  # tests non-default child/infant extraction
            "infants": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Business class from Paris to New York on 2026-11-03, 1 adult.",
        "expected": {
            "origin": {"CDG", "ORY", "PAR"},
            "destination": {"JFK", "EWR", "LGA", "NYC"},
            "departure_date": "2026-11-03",
            "adults": 1,
            "cabin": "BUSINESS",  # tests a premium cabin, not economy
        },
    },
    {
        # phrased "to London from Dubai" (reversed) to test origin/destination
        # attribution, and London = a multi-airport city (accept any).
        "query": "Economy flight to London from Dubai on 2026-09-28, 1 adult.",
        "expected": {
            "origin": "DXB",
            "destination": {"LHR", "LGW", "STN", "LTN", "LCY", "LON"},
            "departure_date": "2026-09-28",
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "First class round-trip Tokyo to Sydney, out 2026-12-01, back 2026-12-15, 1 adult.",
        "expected": {
            "origin": {"NRT", "HND", "TYO"},
            "destination": "SYD",
            "departure_date": "2026-12-01",
            "return_date": "2026-12-15",
            "adults": 1,
            "cabin": "FIRST",  # tests first class + round-trip together
        },
    },
]
