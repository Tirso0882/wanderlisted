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

DATASET_VERSION = "2.0.0"

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
    # Natural phrasing, cabin synonyms, explicit-airport intent, and age-based
    # passenger classification. Duffel considers travelers aged 12+ adults.
    {
        "query": "My partner and I need premium-economy tickets from Singapore to Seoul on 2026-10-02.",
        "expected": {
            "origin": "SIN",
            "destination": {"ICN", "GMP", "SEL"},
            "departure_date": "2026-10-02",
            "adults": 2,
            "cabin": "PREMIUM_ECONOMY",
        },
    },
    {
        "query": "Round-trip in business class: London Heathrow to New York JFK, outbound October 7, 2026, return October 14, 2026, for two adults.",
        "expected": {
            "origin": "LHR",
            "destination": "JFK",
            "departure_date": "2026-10-07",
            "return_date": "2026-10-14",
            "adults": 2,
            "cabin": "BUSINESS",
        },
    },
    {
        "query": "Solo flight from Milan to Paris on 16 October 2026.",
        "expected": {
            "origin": {"MXP", "LIN", "BGY", "MIL"},
            "destination": {"CDG", "ORY", "PAR"},
            "departure_date": "2026-10-16",
            "adults": 1,
        },
    },
    {
        "query": "On 2026-10-19, get three adults and one child to Cape Town from Nairobi Jomo Kenyatta in economy.",
        "expected": {
            "origin": "NBO",
            "destination": "CPT",
            "departure_date": "2026-10-19",
            "adults": 3,
            "children": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Boston to Orlando on 2026-10-24 in economy for one parent, a 13-year-old, and an 11-year-old.",
        "expected": {
            "origin": "BOS",
            "destination": "MCO",
            "departure_date": "2026-10-24",
            "adults": 2,
            "children": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Two adults are flying Madrid to Tenerife South on 2026-11-06 with our 2-year-old and 10-month-old baby, economy.",
        "expected": {
            "origin": "MAD",
            "destination": "TFS",
            "departure_date": "2026-11-06",
            "adults": 2,
            "children": 1,
            "infants": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Flights Warsaw to Athens, 2026-11-09, for two adults and six-year-old twins.",
        "expected": {
            "origin": "WAW",
            "destination": "ATH",
            "departure_date": "2026-11-09",
            "adults": 2,
            "children": 2,
        },
    },
    {
        "query": "Four colleagues and I need business class from Stockholm Arlanda to Brussels Airport on 2026-11-12.",
        "expected": {
            "origin": "ARN",
            "destination": "BRU",
            "departure_date": "2026-11-12",
            "adults": 5,
            "cabin": "BUSINESS",
        },
    },
    {
        "query": "Just me flying Dublin to Prague on 2026-11-16; cabin does not matter.",
        "expected": {
            "origin": "DUB",
            "destination": "PRG",
            "departure_date": "2026-11-16",
            "adults": 1,
        },
    },
    # Corrections and date reasoning: the final stated constraint must win.
    {
        "query": "Not Manchester; depart from Liverpool John Lennon Airport for Amsterdam on 2026-11-20. One adult, economy.",
        "expected": {
            "origin": "LPL",
            "destination": "AMS",
            "departure_date": "2026-11-20",
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "I first said Barcelona, but change the destination: Lisbon to Madrid on 2026-11-23, 2 adults, economy.",
        "expected": {
            "origin": "LIS",
            "destination": "MAD",
            "departure_date": "2026-11-23",
            "adults": 2,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Edinburgh to Oslo on 2026-09-08 -- sorry, make that 2026-09-09 -- for one adult in economy.",
        "expected": {
            "origin": "EDI",
            "destination": "OSL",
            "departure_date": "2026-09-09",
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Auckland to Sydney round-trip for 2 adults: leave 2026-12-28 and fly home 2027-01-04, economy.",
        "expected": {
            "origin": "AKL",
            "destination": "SYD",
            "departure_date": "2026-12-28",
            "return_date": "2027-01-04",
            "adults": 2,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Premium economy Tokyo to Honolulu for my spouse and me; leave 2027-01-10 and return exactly seven days later.",
        "expected": {
            "origin": {"NRT", "HND", "TYO"},
            "destination": "HNL",
            "departure_date": "2027-01-10",
            "return_date": "2027-01-17",
            "adults": 2,
            "cabin": "PREMIUM_ECONOMY",
        },
    },
    {
        "query": "One economy seat from Toronto Pearson to Mexico City on leap day, February 29, 2028.",
        "expected": {
            "origin": "YYZ",
            "destination": "MEX",
            "departure_date": "2028-02-29",
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Business class from Birmingham, England, to San Jose, Costa Rica, on 4 March 2027, one adult.",
        "expected": {
            "origin": "BHX",
            "destination": "SJO",
            "departure_date": "2027-03-04",
            "adults": 1,
            "cabin": "BUSINESS",
        },
    },
    # Geographic names that are easy to conflate, followed by metro-area cases
    # where several airport codes are genuinely correct.
    {
        "query": "Coach flight from Portland, Oregon, to Portland, Maine, on 2027-03-08 for one adult.",
        "expected": {
            "origin": "PDX",
            "destination": "PWM",
            "departure_date": "2027-03-08",
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Fly from London, Ontario (YXU), to London Heathrow (LHR) on 2027-03-12, 1 adult, economy.",
        "expected": {
            "origin": "YXU",
            "destination": "LHR",
            "departure_date": "2027-03-12",
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Business-class flight from Melbourne, Australia, to Santiago, Chile, on 2027-03-18 for two adults.",
        "expected": {
            "origin": "MEL",
            "destination": "SCL",
            "departure_date": "2027-03-18",
            "adults": 2,
            "cabin": "BUSINESS",
        },
    },
    {
        "query": "My spouse and I need economy flights from Panama City, Florida, to Panama City, Panama, on 2027-03-22.",
        "expected": {
            "origin": "ECP",
            "destination": "PTY",
            "departure_date": "2027-03-22",
            "adults": 2,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Premium economy from Paris to Chicago on 2027-04-02, solo traveler.",
        "expected": {
            "origin": {"CDG", "ORY", "PAR"},
            "destination": {"ORD", "MDW", "CHI"},
            "departure_date": "2027-04-02",
            "adults": 1,
            "cabin": "PREMIUM_ECONOMY",
        },
    },
    {
        "query": "First-class round-trip from Osaka to Rome, out 2027-04-06, back 2027-04-20, for 2 adults.",
        "expected": {
            "origin": {"KIX", "ITM", "UKB", "OSA"},
            "destination": {"FCO", "CIA", "ROM"},
            "departure_date": "2027-04-06",
            "return_date": "2027-04-20",
            "adults": 2,
            "cabin": "FIRST",
        },
    },
    {
        "query": "Two adults, business class, Bangkok to Rio de Janeiro on 2027-04-11.",
        "expected": {
            "origin": {"BKK", "DMK"},
            "destination": {"GIG", "SDU", "RIO"},
            "departure_date": "2027-04-11",
            "adults": 2,
            "cabin": "BUSINESS",
        },
    },
    {
        "query": "Seoul to Milan on 2027-04-15 in premium economy for 2 adults, one child, and one infant.",
        "expected": {
            "origin": {"ICN", "GMP", "SEL"},
            "destination": {"MXP", "LIN", "BGY", "MIL"},
            "departure_date": "2027-04-15",
            "adults": 2,
            "children": 1,
            "infants": 1,
            "cabin": "PREMIUM_ECONOMY",
        },
    },
    # Format and context stress: multilingual input, compact fields, irrelevant
    # cities, home/return wording, out-of-order dates, and a negated cabin.
    {
        "query": "Necesito un vuelo de Madrid a Buenos Aires el 2027-05-05, ida y vuelta; regreso el 2027-05-19, para 2 adultos, en clase turista.",
        "expected": {
            "origin": "MAD",
            "destination": {"EZE", "AEP", "BUE"},
            "departure_date": "2027-05-05",
            "return_date": "2027-05-19",
            "adults": 2,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Route: JFK -> LHR | outbound: 2027-05-11 | return: 2027-05-18 | passengers: 3 adults + 1 infant | cabin: FIRST",
        "expected": {
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": "2027-05-11",
            "return_date": "2027-05-18",
            "adults": 3,
            "infants": 1,
            "cabin": "FIRST",
        },
    },
    {
        "query": "I live in Vienna and my sister is in Zurich, but this trip is Budapest to Dubrovnik on 2027-05-23 for one adult, economy.",
        "expected": {
            "origin": "BUD",
            "destination": "DBV",
            "departure_date": "2027-05-23",
            "adults": 1,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "I am based in Marrakech and need a round-trip to Glasgow: fly there on 2027-06-03 and come back home on 2027-06-10, 1 adult.",
        "expected": {
            "origin": "RAK",
            "destination": "GLA",
            "departure_date": "2027-06-03",
            "return_date": "2027-06-10",
            "adults": 1,
        },
    },
    {
        "query": "The return from Boston to Dublin is 2027-06-20; the outbound from Dublin to Boston is 2027-06-07. Two adults, economy.",
        "expected": {
            "origin": "DUB",
            "destination": "BOS",
            "departure_date": "2027-06-07",
            "return_date": "2027-06-20",
            "adults": 2,
            "cabin": "ECONOMY",
        },
    },
    {
        "query": "Frankfurt to Dubai International on 2027-06-25. Premium economy, not business. One adult.",
        "expected": {
            "origin": "FRA",
            "destination": "DXB",
            "departure_date": "2027-06-25",
            "adults": 1,
            "cabin": "PREMIUM_ECONOMY",
        },
    },
]
