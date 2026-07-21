"""Golden dataset for the HOTELS agent — component level (one dataset per agent).

Each item has a stable name, coverage tags, a query, and its expected decision.
`expected` is GROUND TRUTH written from the task, never copied from an agent run.

Conventions:
    - city uses the IATA city/metro location code (Paris = PAR, not CDG). For a
        single-airport city, the airport and city location code can be identical.
    - adults/children are closed-world occupancy labels: all guests in the query
        must be represented, and every child must have exactly one age.
    - max_rate is the total-stay cap. Per-night budgets are multiplied by nights.
    - Omitted stars, board, and budget mean the agent must NOT invent that filter.
        Their positive evaluator skips; no_unrequested_filters enforces absence.

Scope: this dataset is the SEARCH decision only.
# TODO: booking-intent scenario (check_hotel_rate) = a separate thing-under-test
#       with its own dataset — not mixed in here.
"""

from __future__ import annotations

DATASET_VERSION = "2.0.0"
DATASET_SIZE = 40

DATASET: list[dict] = [
    {
        # the real observed case — a star-rating filter.
        "name": "bogota-star-minimum",
        "tags": ["baseline", "stars"],
        "query": "Find hotels in Bogota for 2027-01-05 to 2027-01-13 for 1 adult, 4 stars or higher.",
        "expected": {
            "city": "BOG",
            "check_in": "2027-01-05",
            "check_out": "2027-01-13",
            "adults": 1,
            "children": 0,
            "min_category": 4,
        },
    },
    {
        # board filter: "all-inclusive" -> board code AI.
        "name": "cancun-all-inclusive",
        "tags": ["board", "baseline"],
        "query": "All-inclusive resort in Cancun, 2027-01-15 to 2027-01-22, 2 adults.",
        "expected": {
            "city": "CUN",
            "check_in": "2027-01-15",
            "check_out": "2027-01-22",
            "adults": 2,
            "children": 0,
            "board": "AI",
        },
    },
    {
        # children + ages: the tool needs children_ages when children > 0.
        "name": "lisbon-single-child",
        "tags": ["occupancy", "child-ages"],
        "query": "Hotel in Lisbon for 2 adults and a 6-year-old, 2027-01-25 to 2027-01-29.",
        "expected": {
            "city": "LIS",
            "check_in": "2027-01-25",
            "check_out": "2027-01-29",
            "adults": 2,
            "children": 1,
            "children_ages": [6],
        },
    },
    {
        # budget cap: max_rate is a TOTAL price filter.
        "name": "rome-total-budget",
        "tags": ["budget", "total-budget"],
        "query": "Hotel in Rome, 2027-02-01 to 2027-02-04, 2 adults, total budget 600 EUR.",
        "expected": {
            "city": "ROM",
            "check_in": "2027-02-01",
            "check_out": "2027-02-04",
            "adults": 2,
            "children": 0,
            "max_rate": 600,
        },
    },
    {
        # hotel-specific trap: use the CITY code PAR, not an airport (CDG/ORY).
        "name": "paris-metro-code",
        "tags": ["geography", "metro-code", "unsupported-proximity"],
        "query": "Hotel in Paris near the city center, 2027-02-08 to 2027-02-12, 2 adults.",
        "expected": {
            "city": "PAR",
            "check_in": "2027-02-08",
            "check_out": "2027-02-12",
            "adults": 2,
            "children": 0,
        },
    },
    # ── adversarial cases: built to try to FORCE a FAIL / exercise thin checks ──
    {
        # HARD budget: "per night" but the tool's max_rate is a TOTAL. 3 nights x
        # EUR 120 = 360. Passing 120 (treating per-night as total) is WRONG.
        "name": "vienna-nightly-budget",
        "tags": ["budget", "budget-arithmetic"],
        "query": "Hotel in Vienna for 2 adults, 2027-02-15 to 2027-02-18, under 120 EUR per night.",
        "expected": {
            "city": "VIE",
            "check_in": "2027-02-15",
            "check_out": "2027-02-18",
            "adults": 2,
            "children": 0,
            "max_rate": 360,
        },
    },
    {
        # French phrasing plus board variety: "demi-pension" -> HB.
        "name": "marrakech-french-half-board",
        "tags": ["board", "multilingual", "natural-date"],
        "query": "Je cherche un hôtel en demi-pension à Marrakech du 22 février 2027 au 26 février 2027 pour 2 adultes.",
        "expected": {
            "city": "RAK",
            "check_in": "2027-02-22",
            "check_out": "2027-02-26",
            "adults": 2,
            "children": 0,
            "board": "HB",
        },
    },
    {
        # airport-vs-city trap (the ROM/FCO pattern): Milan's CITY code is MIL,
        # not an airport (MXP/LIN/BGY).
        "name": "milan-metro-code",
        "tags": ["geography", "metro-code"],
        "query": "Hotel in Milan, 2027-03-01 to 2027-03-04, 2 adults.",
        "expected": {
            "city": "MIL",
            "check_in": "2027-03-01",
            "check_out": "2027-03-04",
            "adults": 2,
            "children": 0,
        },
    },
    {
        # two children with specific ages -> children=2 AND children_ages="4,9".
        "name": "athens-two-child-ages",
        "tags": ["occupancy", "child-ages"],
        "query": "Hotel in Athens for 2 adults and two children aged 4 and 9, 2027-03-08 to 2027-03-12.",
        "expected": {
            "city": "ATH",
            "check_in": "2027-03-08",
            "check_out": "2027-03-12",
            "adults": 2,
            "children": 2,
            "children_ages": [4, 9],
        },
    },
    {
        # Combined star + board filters on a multi-airport city code.
        "name": "tokyo-stars-and-breakfast",
        "tags": ["geography", "metro-code", "stars", "board", "interaction"],
        "query": "Five-star hotel in Tokyo with breakfast, 2027-03-15 to 2027-03-18, 1 adult.",
        "expected": {
            "city": "TYO",
            "check_in": "2027-03-15",
            "check_out": "2027-03-18",
            "adults": 1,
            "children": 0,
            "min_category": 5,
            "board": "BB",
        },
    },
    {
        # Room-only + per-night budget conversion: 4 nights x EUR 150 = 600 total.
        "name": "dubai-room-only-nightly-budget",
        "tags": ["board", "budget", "budget-arithmetic", "interaction"],
        "query": "Room-only hotel in Dubai for 2 adults, 2027-03-22 to 2027-03-26, under 150 EUR per night.",
        "expected": {
            "city": "DXB",
            "check_in": "2027-03-22",
            "check_out": "2027-03-26",
            "adults": 2,
            "children": 0,
            "board": "RO",
            "max_rate": 600,
        },
    },
    {
        # Group occupancy + a second star-rating reference.
        "name": "barcelona-group-stars",
        "tags": ["occupancy", "stars", "interaction"],
        "query": "Three-star or better hotel in Barcelona for 3 adults, 2027-03-29 to 2027-04-02.",
        "expected": {
            "city": "BCN",
            "check_in": "2027-03-29",
            "check_out": "2027-04-02",
            "adults": 3,
            "children": 0,
            "min_category": 3,
        },
    },
    {
        # A second exact child-age case.
        "name": "orlando-single-child-age",
        "tags": ["occupancy", "child-ages"],
        "query": "Hotel in Orlando for 2 adults and one child aged 3, 2027-04-05 to 2027-04-09.",
        "expected": {
            "city": "ORL",
            "check_in": "2027-04-05",
            "check_out": "2027-04-09",
            "adults": 2,
            "children": 1,
            "children_ages": [3],
        },
    },
    {
        # Full-board completes the common board-code surface (RO/BB/HB/FB/AI).
        "name": "prague-full-board",
        "tags": ["board"],
        "query": "Full-board hotel in Prague for 2 adults, 2027-04-12 to 2027-04-16.",
        "expected": {
            "city": "PRG",
            "check_in": "2027-04-12",
            "check_out": "2027-04-16",
            "adults": 2,
            "children": 0,
            "board": "FB",
        },
    },
    # Geographic resolution: metro codes and same-name cities must not collapse
    # into a nearby airport or the better-known namesake.
    {
        "name": "new-york-metro-code",
        "tags": ["geography", "metro-code"],
        "query": "Find a hotel in Manhattan, New York City, from 2027-01-05 to 2027-01-09 for 2 adults.",
        "expected": {
            "city": "NYC",
            "check_in": "2027-01-05",
            "check_out": "2027-01-09",
            "adults": 2,
            "children": 0,
        },
    },
    {
        "name": "london-metro-code",
        "tags": ["geography", "metro-code"],
        "query": "Central London hotel for one adult, 2027-01-12 through 2027-01-15.",
        "expected": {
            "city": "LON",
            "check_in": "2027-01-12",
            "check_out": "2027-01-15",
            "adults": 1,
            "children": 0,
        },
    },
    {
        "name": "seoul-metro-code",
        "tags": ["geography", "metro-code"],
        "query": "Hotel in Seoul for 2 adults from 2027-01-20 to 2027-01-24; no airport hotel.",
        "expected": {
            "city": "SEL",
            "check_in": "2027-01-20",
            "check_out": "2027-01-24",
            "adults": 2,
            "children": 0,
        },
    },
    {
        "name": "osaka-metro-code",
        "tags": ["geography", "metro-code"],
        "query": "Stay in Osaka city from 2027-01-27 to 2027-01-30 for one adult, not specifically near Kansai Airport.",
        "expected": {
            "city": "OSA",
            "check_in": "2027-01-27",
            "check_out": "2027-01-30",
            "adults": 1,
            "children": 0,
        },
    },
    {
        "name": "san-jose-costa-rica-disambiguation",
        "tags": ["geography", "namesake", "negative-constraint"],
        "query": "Hotel in San Jose, Costa Rica - not San Jose, California - from 2027-02-02 to 2027-02-06 for 2 adults.",
        "expected": {
            "city": "SJO",
            "check_in": "2027-02-02",
            "check_out": "2027-02-06",
            "adults": 2,
            "children": 0,
        },
    },
    {
        "name": "portland-maine-disambiguation",
        "tags": ["geography", "namesake", "negative-constraint"],
        "query": "I need a Portland, Maine hotel, not Portland, Oregon: 2027-02-09 to 2027-02-12 for 1 adult.",
        "expected": {
            "city": "PWM",
            "check_in": "2027-02-09",
            "check_out": "2027-02-12",
            "adults": 1,
            "children": 0,
        },
    },
    {
        "name": "panama-city-country-disambiguation",
        "tags": ["geography", "namesake", "negative-constraint"],
        "query": "Hotel in Panama City, Panama (not Panama City, Florida), 2027-02-15 to 2027-02-19, for 2 adults.",
        "expected": {
            "city": "PTY",
            "check_in": "2027-02-15",
            "check_out": "2027-02-19",
            "adults": 2,
            "children": 0,
        },
    },
    {
        "name": "london-ontario-disambiguation",
        "tags": ["geography", "namesake", "negative-constraint"],
        "query": "Find a hotel in London, Ontario, Canada - not London, England - for 1 adult from 2027-02-22 to 2027-02-25.",
        "expected": {
            "city": "YXU",
            "check_in": "2027-02-22",
            "check_out": "2027-02-25",
            "adults": 1,
            "children": 0,
        },
    },
    # Date reasoning: cross-year/month stays, inferred duration, reversed mention
    # order, and a correction where only the final dates are authoritative.
    {
        "name": "edinburgh-year-rollover",
        "tags": ["date-reasoning", "year-boundary", "natural-date"],
        "query": "Edinburgh hotel for 2 adults: check in December 30, 2026 and check out January 3, 2027.",
        "expected": {
            "city": "EDI",
            "check_in": "2026-12-30",
            "check_out": "2027-01-03",
            "adults": 2,
            "children": 0,
        },
    },
    {
        "name": "helsinki-month-boundary",
        "tags": ["date-reasoning", "month-boundary", "natural-date"],
        "query": "One adult needs a Helsinki hotel from February 28 to March 2, 2027.",
        "expected": {
            "city": "HEL",
            "check_in": "2027-02-28",
            "check_out": "2027-03-02",
            "adults": 1,
            "children": 0,
        },
    },
    {
        "name": "amsterdam-duration-derived-checkout",
        "tags": ["date-reasoning", "duration-arithmetic", "natural-date"],
        "query": "Book a five-night Amsterdam hotel stay starting May 28, 2027, for 2 adults.",
        "expected": {
            "city": "AMS",
            "check_in": "2027-05-28",
            "check_out": "2027-06-02",
            "adults": 2,
            "children": 0,
        },
    },
    {
        "name": "copenhagen-dates-mentioned-out-of-order",
        "tags": ["date-reasoning", "out-of-order"],
        "query": "The Copenhagen checkout is 2027-03-12; check-in is 2027-03-08. The room is for 2 adults.",
        "expected": {
            "city": "CPH",
            "check_in": "2027-03-08",
            "check_out": "2027-03-12",
            "adults": 2,
            "children": 0,
        },
    },
    {
        "name": "oslo-date-correction",
        "tags": ["date-reasoning", "correction"],
        "query": "Oslo hotel for one adult from 2027-05-21 to 2027-05-24 - sorry, make that 2027-05-22 to 2027-05-25.",
        "expected": {
            "city": "OSL",
            "check_in": "2027-05-22",
            "check_out": "2027-05-25",
            "adults": 1,
            "children": 0,
        },
    },
    # Occupancy language: corrections, inferred group counts, twins, age zero,
    # and teenagers all have deterministic Hotelbeds child paxes.
    {
        "name": "berlin-guest-correction",
        "tags": ["occupancy", "correction", "negative-constraint"],
        "query": "Berlin hotel, 2027-03-15 to 2027-03-18. I first said 2 adults and 2 children; correction: only 1 adult, no children.",
        "expected": {
            "city": "BER",
            "check_in": "2027-03-15",
            "check_out": "2027-03-18",
            "adults": 1,
            "children": 0,
        },
    },
    {
        "name": "madrid-three-couples",
        "tags": ["occupancy", "natural-count"],
        "query": "A Madrid hotel for three couples from 2027-03-21 to 2027-03-24; there are no children.",
        "expected": {
            "city": "MAD",
            "check_in": "2027-03-21",
            "check_out": "2027-03-24",
            "adults": 6,
            "children": 0,
        },
    },
    {
        "name": "warsaw-six-year-old-twins",
        "tags": ["occupancy", "child-ages", "natural-count"],
        "query": "Warsaw hotel for two adults and six-year-old twins, 2027-03-27 to 2027-03-31.",
        "expected": {
            "city": "WAW",
            "check_in": "2027-03-27",
            "check_out": "2027-03-31",
            "adults": 2,
            "children": 2,
            "children_ages": [6, 6],
        },
    },
    {
        "name": "miami-infant-age-zero",
        "tags": ["occupancy", "child-ages", "boundary-value"],
        "query": "Miami hotel for 2 adults and our 10-month-old baby, 2027-04-03 to 2027-04-07.",
        "expected": {
            "city": "MIA",
            "check_in": "2027-04-03",
            "check_out": "2027-04-07",
            "adults": 2,
            "children": 1,
            "children_ages": [0],
        },
    },
    {
        "name": "toronto-teen-and-child-ages",
        "tags": ["occupancy", "child-ages", "boundary-value", "metro-code"],
        "query": "Toronto hotel for 2 adults and our children aged 13 and 7, from 2027-04-10 to 2027-04-14.",
        "expected": {
            "city": "YTO",
            "check_in": "2027-04-10",
            "check_out": "2027-04-14",
            "adults": 2,
            "children": 2,
            "children_ages": [13, 7],
        },
    },
    # Filter language, corrections, arithmetic, distractors, and dense format.
    {
        "name": "punta-cana-spanish-all-inclusive",
        "tags": ["board", "multilingual", "natural-date"],
        "query": "Busco un hotel todo incluido en Punta Cana del 17 al 24 de abril de 2027 para 2 adultos.",
        "expected": {
            "city": "PUJ",
            "check_in": "2027-04-17",
            "check_out": "2027-04-24",
            "adults": 2,
            "children": 0,
            "board": "AI",
        },
    },
    {
        "name": "antalya-board-correction",
        "tags": ["board", "correction", "negative-constraint"],
        "query": "Antalya hotel for 2 adults, 2027-04-26 to 2027-04-30. Not all-inclusive after all; breakfast included only.",
        "expected": {
            "city": "AYT",
            "check_in": "2027-04-26",
            "check_out": "2027-04-30",
            "adults": 2,
            "children": 0,
            "board": "BB",
        },
    },
    {
        "name": "brussels-star-correction",
        "tags": ["stars", "correction"],
        "query": "Brussels hotel for one adult, 2027-05-03 to 2027-05-06. I initially asked for five stars, but change that to three stars or better.",
        "expected": {
            "city": "BRU",
            "check_in": "2027-05-03",
            "check_out": "2027-05-06",
            "adults": 1,
            "children": 0,
            "min_category": 3,
        },
    },
    {
        "name": "florence-budget-correction",
        "tags": ["budget", "budget-arithmetic", "correction"],
        "query": "Florence hotel for 2 adults, 2027-05-09 to 2027-05-13. Ignore my earlier 900 EUR total cap; use 175 EUR per night instead.",
        "expected": {
            "city": "FLR",
            "check_in": "2027-05-09",
            "check_out": "2027-05-13",
            "adults": 2,
            "children": 0,
            "max_rate": 700,
        },
    },
    {
        "name": "sydney-thousands-separator-budget",
        "tags": ["budget", "number-format"],
        "query": "Sydney hotel from 2027-05-16 to 2027-05-20 for 2 adults, maximum total stay price 1,200 AUD.",
        "expected": {
            "city": "SYD",
            "check_in": "2027-05-16",
            "check_out": "2027-05-20",
            "adults": 2,
            "children": 0,
            "max_rate": 1200,
        },
    },
    {
        "name": "lisbon-flight-detail-distractors",
        "tags": ["budget", "context-resistance", "numeric-distractor"],
        "query": "My flight cost 900 EUR and lands on 2027-05-31. For the hotel itself, Lisbon from 2027-06-01 to 2027-06-04, 2 adults, cap the total hotel price at 500 EUR.",
        "expected": {
            "city": "LIS",
            "check_in": "2027-06-01",
            "check_out": "2027-06-04",
            "adults": 2,
            "children": 0,
            "max_rate": 500,
        },
    },
    {
        "name": "new-york-compact-all-fields",
        "tags": ["compact-format", "interaction", "stars", "board", "budget", "occupancy"],
        "query": "STAY=NYC | IN=2027-06-08 | OUT=2027-06-11 | GUESTS=2A+1C(age 5) | MIN_STARS=4 | BOARD=BB | MAX_TOTAL=1200",
        "expected": {
            "city": "NYC",
            "check_in": "2027-06-08",
            "check_out": "2027-06-11",
            "adults": 2,
            "children": 1,
            "children_ages": [5],
            "min_category": 4,
            "board": "BB",
            "max_rate": 1200,
        },
    },
    {
        "name": "singapore-explicit-no-preferences",
        "tags": ["negative-constraint", "no-invented-filters", "context-resistance"],
        "query": "Singapore hotel from 2027-06-15 to 2027-06-18 for one adult. I have no star minimum, any meal plan is fine, and the budget is flexible.",
        "expected": {
            "city": "SIN",
            "check_in": "2027-06-15",
            "check_out": "2027-06-18",
            "adults": 1,
            "children": 0,
        },
    },
]
