"""Golden dataset for LangSmith evaluations.

Contains representative travel planning test cases covering all agent
capabilities. Used by `scripts/eval_agents.py` and CI pipelines.

Best practice: ≥30 examples covering every agent type, multiple
destinations, edge cases, and user profiles.
"""

# Each item: inputs dict + reference_outputs dict
GOLDEN_DATASET = [
    # ── Flight queries (5) ──────────────────────────────────────────────
    {
        "inputs": {"question": "Find flights from NYC to Tokyo for July 15-22"},
        "outputs": {
            "destinations": ["tokyo"],
            "expected_agents": ["FlightsAgent"],
            "must_contain": ["flight", "JFK", "NRT"],
        },
    },
    {
        "inputs": {"question": "What's the cheapest flight from London to Barcelona next month?"},
        "outputs": {
            "destinations": ["barcelona"],
            "expected_agents": ["FlightsAgent"],
            "must_contain": ["flight", "price"],
        },
    },
    {
        "inputs": {"question": "Direct flights from Miami to Cancun in December?"},
        "outputs": {
            "destinations": ["cancun"],
            "expected_agents": ["FlightsAgent"],
            "must_contain": ["flight", "Cancun"],
        },
    },
    {
        "inputs": {"question": "Flights from Los Angeles to Lima, round trip, economy class"},
        "outputs": {
            "destinations": ["lima"],
            "expected_agents": ["FlightsAgent"],
            "must_contain": ["flight", "Lima"],
        },
    },
    {
        "inputs": {"question": "Business class flights from Frankfurt to Istanbul for next week"},
        "outputs": {
            "destinations": ["istanbul"],
            "expected_agents": ["FlightsAgent"],
            "must_contain": ["flight", "Istanbul"],
        },
    },

    # ── Hotel queries (4) ───────────────────────────────────────────────
    {
        "inputs": {"question": "Recommend budget hotels in Shinjuku area, Tokyo"},
        "outputs": {
            "destinations": ["tokyo"],
            "expected_agents": ["HotelsAgent"],
            "must_contain": ["Shinjuku", "hotel", "price"],
        },
    },
    {
        "inputs": {"question": "Best boutique hotels near the Colosseum in Rome"},
        "outputs": {
            "destinations": ["rome"],
            "expected_agents": ["HotelsAgent"],
            "must_contain": ["hotel", "Rome"],
        },
    },
    {
        "inputs": {"question": "Family-friendly all-inclusive resorts in Cancun hotel zone"},
        "outputs": {
            "destinations": ["cancun"],
            "expected_agents": ["HotelsAgent"],
            "must_contain": ["hotel", "Cancun"],
        },
    },
    {
        "inputs": {"question": "Affordable hostels near La Rambla in Barcelona"},
        "outputs": {
            "destinations": ["barcelona"],
            "expected_agents": ["HotelsAgent"],
            "must_contain": ["hostel", "Barcelona"],
        },
    },

    # ── Destination / RAG queries (4) ───────────────────────────────────
    {
        "inputs": {"question": "What temples should I visit in Bangkok?"},
        "outputs": {
            "destinations": ["bangkok"],
            "expected_agents": ["DestinationAgent"],
            "must_contain": ["Wat Pho", "temple"],
        },
    },
    {
        "inputs": {"question": "Is it safe to travel to Cairo right now?"},
        "outputs": {
            "destinations": ["cairo"],
            "expected_agents": ["DestinationAgent"],
            "must_contain": ["safety"],
        },
    },
    {
        "inputs": {"question": "What's the best time of year to visit Kraków?"},
        "outputs": {
            "destinations": ["krakow"],
            "expected_agents": ["DestinationAgent"],
            "must_contain": ["season", "weather"],
        },
    },
    {
        "inputs": {"question": "What scams should I watch out for in Paris?"},
        "outputs": {
            "destinations": ["paris"],
            "expected_agents": ["DestinationAgent"],
            "must_contain": ["scam", "pickpocket"],
        },
    },

    # ── Restaurant queries (4) ──────────────────────────────────────────
    {
        "inputs": {"question": "Best ramen shops in Tokyo for a foodie"},
        "outputs": {
            "destinations": ["tokyo"],
            "expected_agents": ["RestaurantsAgent"],
            "must_contain": ["ramen", "restaurant"],
        },
    },
    {
        "inputs": {"question": "Where to get authentic street food in Bangkok?"},
        "outputs": {
            "destinations": ["bangkok"],
            "expected_agents": ["RestaurantsAgent"],
            "must_contain": ["food", "Bangkok"],
        },
    },
    {
        "inputs": {"question": "Best steak restaurants in Buenos Aires, Palermo area"},
        "outputs": {
            "destinations": ["buenos_aires"],
            "expected_agents": ["RestaurantsAgent"],
            "must_contain": ["restaurant", "Buenos Aires"],
        },
    },
    {
        "inputs": {"question": "Cheap local eats in Mexico City's Centro Histórico"},
        "outputs": {
            "destinations": ["mexico_city"],
            "expected_agents": ["RestaurantsAgent"],
            "must_contain": ["food", "Mexico"],
        },
    },

    # ── Activities (3) ──────────────────────────────────────────────────
    {
        "inputs": {"question": "What outdoor activities can I do in Cape Town?"},
        "outputs": {
            "destinations": ["cape_town"],
            "expected_agents": ["ActivitiesAgent"],
            "must_contain": ["activi"],
        },
    },
    {
        "inputs": {"question": "Art galleries and museums to visit in Paris"},
        "outputs": {
            "destinations": ["paris"],
            "expected_agents": ["ActivitiesAgent"],
            "must_contain": ["museum", "Paris"],
        },
    },
    {
        "inputs": {"question": "Nightlife options in Medellín for young travelers"},
        "outputs": {
            "destinations": ["medellin"],
            "expected_agents": ["ActivitiesAgent"],
            "must_contain": ["Medellín"],
        },
    },

    # ── Transportation (3) ──────────────────────────────────────────────
    {
        "inputs": {"question": "How do I get from Tokyo to Kyoto? Train options?"},
        "outputs": {
            "destinations": ["tokyo", "kyoto"],
            "expected_agents": ["TransportationAgent"],
            "must_contain": ["shinkansen", "train"],
        },
    },
    {
        "inputs": {"question": "Best way to get from CDG airport to central Paris?"},
        "outputs": {
            "destinations": ["paris"],
            "expected_agents": ["TransportationAgent"],
            "must_contain": ["RER", "airport"],
        },
    },
    {
        "inputs": {"question": "Public transport options in Istanbul, is there a metro card?"},
        "outputs": {
            "destinations": ["istanbul"],
            "expected_agents": ["TransportationAgent"],
            "must_contain": ["Istanbulkart", "metro"],
        },
    },

    # ── Multi-agent full pipeline (6) ───────────────────────────────────
    {
        "inputs": {
            "question": (
                "Plan a 5-day trip to Barcelona for a couple, moderate budget, "
                "interested in art and food"
            ),
        },
        "outputs": {
            "destinations": ["barcelona"],
            "expected_agents": [
                "FlightsAgent", "HotelsAgent", "DestinationAgent",
                "RestaurantsAgent", "ActivitiesAgent", "TransportationAgent",
                "BudgetAgent", "ItineraryAgent",
            ],
            "travel_style": "moderate",
            "must_contain": ["Barcelona", "day 1", "budget"],
        },
    },
    {
        "inputs": {
            "question": (
                "Plan a 7-day family trip to Tokyo and Kyoto, $5000 budget, "
                "2 adults 2 kids, interested in culture and nature"
            ),
        },
        "outputs": {
            "destinations": ["tokyo", "kyoto"],
            "expected_agents": [
                "FlightsAgent", "HotelsAgent", "DestinationAgent",
                "RestaurantsAgent", "ActivitiesAgent", "TransportationAgent",
                "BudgetAgent", "ItineraryAgent",
            ],
            "travel_style": "mid-range",
            "group_type": "family",
            "must_contain": ["Tokyo", "Kyoto", "day 1", "budget"],
        },
    },
    {
        "inputs": {
            "question": (
                "Plan a 4-day solo trip to Rome, luxury budget, "
                "history and fine dining focus"
            ),
        },
        "outputs": {
            "destinations": ["rome"],
            "expected_agents": [
                "FlightsAgent", "HotelsAgent", "DestinationAgent",
                "RestaurantsAgent", "ActivitiesAgent", "TransportationAgent",
                "BudgetAgent", "ItineraryAgent",
            ],
            "travel_style": "luxury",
            "must_contain": ["Rome", "day 1", "budget"],
        },
    },
    {
        "inputs": {
            "question": (
                "Plan a 10-day backpacking trip through Lima and Quito, "
                "under $2000 total, adventure and local food"
            ),
        },
        "outputs": {
            "destinations": ["lima", "quito"],
            "expected_agents": [
                "FlightsAgent", "HotelsAgent", "DestinationAgent",
                "RestaurantsAgent", "ActivitiesAgent", "TransportationAgent",
                "BudgetAgent", "ItineraryAgent",
            ],
            "travel_style": "budget",
            "must_contain": ["Lima", "Quito", "day 1", "budget"],
        },
    },
    {
        "inputs": {
            "question": (
                "Plan a 6-day honeymoon in Istanbul, mid-range budget, "
                "romantic restaurants and Bosphorus cruise"
            ),
        },
        "outputs": {
            "destinations": ["istanbul"],
            "expected_agents": [
                "FlightsAgent", "HotelsAgent", "DestinationAgent",
                "RestaurantsAgent", "ActivitiesAgent", "TransportationAgent",
                "BudgetAgent", "ItineraryAgent",
            ],
            "travel_style": "mid-range",
            "group_type": "couple",
            "must_contain": ["Istanbul", "day 1", "budget"],
        },
    },
    {
        "inputs": {
            "question": (
                "Plan 3 days in Tallinn, Estonia for a group of friends, "
                "budget trip, interested in medieval history and nightlife"
            ),
        },
        "outputs": {
            "destinations": ["tallinn"],
            "expected_agents": [
                "FlightsAgent", "HotelsAgent", "DestinationAgent",
                "RestaurantsAgent", "ActivitiesAgent", "TransportationAgent",
                "BudgetAgent", "ItineraryAgent",
            ],
            "travel_style": "budget",
            "group_type": "friends",
            "must_contain": ["Tallinn", "day 1", "budget"],
        },
    },

    # ── Shallow queries (should NOT trigger pipeline) (3) ──────────────
    {
        "inputs": {"question": "Thanks!"},
        "outputs": {
            "expected_agents": [],
            "is_shallow": True,
        },
    },
    {
        "inputs": {"question": "Hello, how are you?"},
        "outputs": {
            "expected_agents": [],
            "is_shallow": True,
        },
    },
    {
        "inputs": {"question": "What can you do?"},
        "outputs": {
            "expected_agents": [],
            "is_shallow": True,
        },
    },

    # ── Dietary restrictions (2) ────────────────────────────────────────
    {
        "inputs": {"question": "Plan a trip to Tokyo, I'm vegan and gluten-free"},
        "outputs": {
            "destinations": ["tokyo"],
            "dietary_restrictions": ["vegan", "gluten-free"],
            "must_contain": ["vegan", "plant-based"],
        },
    },
    {
        "inputs": {
            "question": (
                "Halal food options for a 5-day trip to London, "
                "family of 4, mid-range budget"
            ),
        },
        "outputs": {
            "destinations": ["london"],
            "dietary_restrictions": ["halal"],
            "must_contain": ["halal", "London"],
        },
    },

    # ── Budget-focused (2) ──────────────────────────────────────────────
    {
        "inputs": {"question": "Plan a budget backpacker trip to Bangkok for 2 weeks, under $1500"},
        "outputs": {
            "destinations": ["bangkok"],
            "travel_style": "budget",
            "must_contain": ["budget", "Bangkok"],
        },
    },
    {
        "inputs": {"question": "How much does a 5-day trip to Cancun cost? Break it down."},
        "outputs": {
            "destinations": ["cancun"],
            "expected_agents": ["BudgetAgent"],
            "must_contain": ["budget", "cost"],
        },
    },

    # ── Accessibility (2) ───────────────────────────────────────────────
    {
        "inputs": {
            "question": "Plan a wheelchair-accessible trip to Barcelona for 4 days",
        },
        "outputs": {
            "destinations": ["barcelona"],
            "accessibility_needs": ["wheelchair"],
            "must_contain": ["accessib"],
        },
    },
    {
        "inputs": {
            "question": (
                "Traveling with elderly parents to Rome, "
                "need mobility-friendly activities and hotels"
            ),
        },
        "outputs": {
            "destinations": ["rome"],
            "accessibility_needs": ["mobility"],
            "must_contain": ["Rome"],
        },
    },
]
