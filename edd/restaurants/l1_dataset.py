"""Golden decision dataset for the Restaurants agent.

Each case labels only constraints stated in the request. Evaluators accept sets
of semantically equivalent search terms because Google Places takes free text,
not a fixed restaurant taxonomy. A list of sets means every concept group is
required across the search set; one search may satisfy several groups. Omitted
constraints are not applicable.
"""

from __future__ import annotations

DATASET_VERSION = "1.0.0"

DATASET: list[dict] = [
    {
        "name": "tokyo-sushi-neighborhood",
        "query": "Find the best sushi restaurants in Shinjuku, Tokyo.",
        "expected": {
            "location": {"tokyo", "shinjuku"},
            "area": {"shinjuku"},
            "cuisine": {"sushi", "japanese"},
            "venue_type": {"restaurant", "sushi"},
        },
    },
    {
        "name": "rome-vegetarian",
        "query": "Recommend vegetarian restaurants in central Rome.",
        "expected": {
            "location": {"rome"},
            "area": {
                "central rome",
                "rome center",
                "rome centre",
                "rome city center",
                "rome city centre",
            },
            "dietary": {"vegetarian", "plant based"},
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "istanbul-halal-street-food",
        "query": "Find halal street food and food markets in Istanbul.",
        "expected": {
            "location": {"istanbul"},
            "dietary": {"halal"},
            "venue_type": [{"street food"}, {"food market", "market"}],
        },
    },
    {
        "name": "paris-gluten-free-cafes",
        "query": "Gluten-free cafes and bakeries in Paris, please.",
        "expected": {
            "location": {"paris"},
            "dietary": {"gluten free", "celiac", "coeliac"},
            "venue_type": [{"cafe"}, {"bakery"}],
        },
    },
    {
        "name": "mexico-city-budget",
        "query": "Cheap local eats around Roma Norte in Mexico City.",
        "expected": {
            "location": {"mexico city", "roma norte", "ciudad de mexico"},
            "area": {"roma norte"},
            "price_style": {
                "cheap",
                "budget",
                "affordable",
                "inexpensive",
                "street food",
            },
        },
    },
    {
        "name": "copenhagen-fine-dining",
        "query": "Michelin-starred fine dining in Copenhagen for a luxury trip.",
        "expected": {
            "location": {"copenhagen"},
            "venue_type": {"restaurant", "fine dining"},
            "price_style": {"michelin", "michelin starred"},
        },
    },
    {
        "name": "paris-family-eiffel",
        "query": "Kid-friendly restaurants near the Eiffel Tower in Paris.",
        "expected": {
            "location": {"paris", "eiffel tower"},
            "area": {"eiffel tower"},
            "venue_type": {"restaurant"},
            "group_fit": {
                "kid friendly",
                "family friendly",
                "children",
                "families",
            },
        },
    },
    {
        "name": "barcelona-bars",
        "query": "Recommend cocktail bars in El Born, Barcelona.",
        "expected": {
            "location": {"barcelona", "el born"},
            "area": {"el born"},
            "venue_type": {"cocktail bar", "bar"},
        },
    },
    {
        "name": "bangkok-markets",
        "query": "What are the best food markets and street-food areas in Bangkok?",
        "expected": {
            "location": {"bangkok"},
            "venue_type": [{"food market", "market"}, {"street food"}],
        },
    },
    {
        "name": "kyoto-vegan-ramen",
        "query": "Find vegan ramen in Kyoto.",
        "expected": {
            "location": {"kyoto"},
            "cuisine": {"ramen", "japanese"},
            "dietary": {"vegan", "plant based"},
            "venue_type": {"restaurant", "ramen"},
        },
    },
    {
        "name": "lisbon-large-group",
        "query": "Restaurants in Lisbon that can handle a group of 12 people.",
        "expected": {
            "location": {"lisbon"},
            "venue_type": {"restaurant"},
            "group_fit": {
                "large group",
                "group of 12",
                "12 people",
                "group dining",
                "groups",
            },
        },
    },
    {
        "name": "lisbon-seafood-alfama",
        "query": "Traditional Portuguese seafood restaurants in Alfama, Lisbon.",
        "expected": {
            "location": {"lisbon", "alfama"},
            "area": {"alfama"},
            "cuisine": [{"portuguese"}, {"seafood"}],
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "new-orleans-creole-brunch",
        "query": "Find Creole brunch restaurants in the French Quarter, New Orleans.",
        "expected": {
            "location": {"new orleans", "french quarter"},
            "area": {"french quarter"},
            "cuisine": {"creole"},
            "venue_type": {"brunch"},
        },
    },
    {
        "name": "barcelona-explicit-radius",
        "query": "Restaurants within 800 metres of Sagrada Familia in Barcelona.",
        "expected": {
            "location": {"barcelona", "sagrada familia"},
            "area": {"sagrada familia"},
            "venue_type": {"restaurant"},
            "max_radius_meters": 800,
            "proximity_location": {"sagrada familia"},
        },
    },
    {
        "name": "amsterdam-indonesian-jordaan",
        "query": "Indonesian rijsttafel restaurants in the Jordaan, Amsterdam.",
        "expected": {
            "location": {"amsterdam", "jordaan"},
            "area": {"jordaan"},
            "cuisine": {"indonesian", "rijsttafel"},
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "seoul-korean-bbq-gangnam",
        "query": "Korean barbecue restaurants in Gangnam, Seoul.",
        "expected": {
            "location": {"seoul", "gangnam"},
            "area": {"gangnam"},
            "cuisine": {"korean barbecue", "korean bbq", "bbq"},
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "singapore-hawker-street-food",
        "query": "Hawker centres and street-food markets in Singapore.",
        "expected": {
            "location": {"singapore"},
            "venue_type": [
                {"hawker centre", "hawker center", "food court", "market"},
                {"street food"},
            ],
        },
    },
    {
        "name": "berlin-vegan-breakfast",
        "query": "Vegan breakfast cafes in Berlin.",
        "expected": {
            "location": {"berlin"},
            "dietary": {"vegan", "plant based"},
            "venue_type": [{"breakfast"}, {"cafe"}],
        },
    },
    {
        "name": "mumbai-vegetarian-thali",
        "query": "Vegetarian Indian thali restaurants in Mumbai.",
        "expected": {
            "location": {"mumbai"},
            "cuisine": [{"indian"}, {"thali"}],
            "dietary": {"vegetarian", "plant based"},
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "dubai-halal-family-marina",
        "query": "Halal family-friendly restaurants in Dubai Marina.",
        "expected": {
            "location": {"dubai", "dubai marina"},
            "area": {"dubai marina"},
            "dietary": {"halal"},
            "venue_type": {"restaurant"},
            "group_fit": {
                "family friendly",
                "kid friendly",
                "children",
                "families",
            },
        },
    },
    {
        "name": "toronto-brunch-distillery",
        "query": "Brunch restaurants in Toronto's Distillery District.",
        "expected": {
            "location": {"toronto", "distillery district"},
            "area": {"distillery district"},
            "venue_type": {"brunch", "brunch restaurant"},
        },
    },
    {
        "name": "buenos-aires-steak-palermo",
        "query": "Argentinian steakhouses in Palermo, Buenos Aires.",
        "expected": {
            "location": {"buenos aires", "palermo"},
            "area": {"palermo"},
            "cuisine": {"argentinian", "steak", "steakhouse"},
            "venue_type": {"restaurant", "steakhouse"},
        },
    },
    {
        "name": "lima-ceviche-miraflores",
        "query": "Peruvian ceviche restaurants in Miraflores, Lima.",
        "expected": {
            "location": {"lima", "miraflores"},
            "area": {"miraflores"},
            "cuisine": {"peruvian", "ceviche"},
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "marrakech-luxury-rooftop-medina",
        "query": "Luxury rooftop restaurants in the Medina of Marrakech.",
        "expected": {
            "location": {"marrakech", "medina"},
            "area": {"medina"},
            "venue_type": {"restaurant", "rooftop restaurant"},
            "price_style": {"luxury", "upscale", "fine dining"},
        },
    },
    {
        "name": "athens-budget-tavernas-plaka",
        "query": "Cheap Greek tavernas in Plaka, Athens.",
        "expected": {
            "location": {"athens", "plaka"},
            "area": {"plaka"},
            "cuisine": {"greek", "taverna"},
            "venue_type": {"taverna", "restaurant"},
            "price_style": {"cheap", "budget", "affordable", "inexpensive"},
        },
    },
    {
        "name": "cape-town-seafood-waterfront",
        "query": "Seafood restaurants at the V&A Waterfront in Cape Town.",
        "expected": {
            "location": {"cape town", "v a waterfront", "waterfront"},
            "area": {"v a waterfront", "waterfront"},
            "cuisine": {"seafood"},
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "sydney-gluten-free-bakeries-cafes",
        "query": "Gluten-free bakeries and cafes in Sydney.",
        "expected": {
            "location": {"sydney"},
            "dietary": {"gluten free", "celiac", "coeliac"},
            "venue_type": [{"bakery"}, {"cafe"}],
        },
    },
    {
        "name": "melbourne-coffee-fitzroy",
        "query": "Independent coffee shops in Fitzroy, Melbourne.",
        "expected": {
            "location": {"melbourne", "fitzroy"},
            "area": {"fitzroy"},
            "venue_type": {"coffee shop", "cafe"},
        },
    },
    {
        "name": "chicago-deep-dish",
        "query": "Deep-dish pizza restaurants in Chicago.",
        "expected": {
            "location": {"chicago"},
            "cuisine": {"deep dish", "pizza"},
            "venue_type": {"pizza restaurant", "restaurant"},
        },
    },
    {
        "name": "montreal-poutine-old-montreal",
        "query": "Poutine restaurants in Old Montreal.",
        "expected": {
            "location": {"montreal", "old montreal"},
            "area": {"old montreal"},
            "cuisine": {"poutine", "quebecois", "canadian"},
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "hong-kong-dim-sum-central",
        "query": "Cantonese dim sum restaurants in Central, Hong Kong.",
        "expected": {
            "location": {"hong kong", "central"},
            "area": {"central"},
            "cuisine": {"cantonese", "dim sum"},
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "hanoi-street-food-old-quarter",
        "query": "Street-food stalls in Hanoi's Old Quarter.",
        "expected": {
            "location": {"hanoi", "old quarter"},
            "area": {"old quarter"},
            "venue_type": {"street food", "food stall"},
        },
    },
    {
        "name": "bali-vegan-cafes-canggu",
        "query": "Vegan cafes and restaurants in Canggu, Bali.",
        "expected": {
            "location": {"bali", "canggu"},
            "area": {"canggu"},
            "dietary": {"vegan", "plant based"},
            "venue_type": [{"cafe"}, {"restaurant"}],
        },
    },
    {
        "name": "osaka-okonomiyaki-dotonbori",
        "query": "Okonomiyaki restaurants in Dotonbori, Osaka.",
        "expected": {
            "location": {"osaka", "dotonbori"},
            "area": {"dotonbori"},
            "cuisine": {"okonomiyaki", "japanese"},
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "stockholm-michelin-fine-dining",
        "query": "Michelin-starred fine dining in Stockholm.",
        "expected": {
            "location": {"stockholm"},
            "venue_type": {"fine dining", "restaurant"},
            "price_style": {"michelin", "michelin starred"},
        },
    },
    {
        "name": "prague-beer-halls-old-town",
        "query": "Traditional beer halls and pubs in Prague Old Town.",
        "expected": {
            "location": {"prague", "old town"},
            "area": {"old town"},
            "venue_type": {"beer hall", "pub"},
        },
    },
    {
        "name": "vienna-coffeehouses-innere-stadt",
        "query": "Traditional Viennese coffeehouses in Innere Stadt, Vienna.",
        "expected": {
            "location": {"vienna", "innere stadt"},
            "area": {"innere stadt", "first district"},
            "cuisine": {"viennese", "austrian"},
            "venue_type": {"coffeehouse", "coffee shop", "cafe"},
        },
    },
    {
        "name": "edinburgh-whisky-bars-royal-mile",
        "query": "Whisky bars near the Royal Mile in Edinburgh.",
        "expected": {
            "location": {"edinburgh", "royal mile"},
            "area": {"royal mile"},
            "venue_type": {"whisky bar", "whiskey bar", "bar"},
        },
    },
    {
        "name": "rio-churrascaria-copacabana",
        "query": "Brazilian churrascarias in Copacabana, Rio de Janeiro.",
        "expected": {
            "location": {"rio de janeiro", "copacabana", "rio"},
            "area": {"copacabana"},
            "cuisine": {"brazilian", "churrascaria", "barbecue"},
            "venue_type": {"restaurant", "steakhouse"},
        },
    },
    {
        "name": "johannesburg-halal-south-african",
        "query": "Halal South African restaurants in Johannesburg.",
        "expected": {
            "location": {"johannesburg"},
            "cuisine": {"south african"},
            "dietary": {"halal"},
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "delhi-large-group-15",
        "query": "Restaurants in New Delhi for a group of 15 people.",
        "expected": {
            "location": {"new delhi", "delhi"},
            "venue_type": {"restaurant"},
            "group_fit": {
                "large group",
                "group of 15",
                "15 people",
                "group dining",
                "groups",
            },
        },
    },
    {
        "name": "istanbul-hagia-sophia-radius",
        "query": "Restaurants within 500 metres of Hagia Sophia in Istanbul.",
        "expected": {
            "location": {"istanbul", "hagia sophia"},
            "area": {"hagia sophia"},
            "venue_type": {"restaurant"},
            "max_radius_meters": 500,
            "proximity_location": {"hagia sophia"},
        },
    },
    {
        "name": "london-british-museum-radius",
        "query": "Cafes within 600 metres of the British Museum in London.",
        "expected": {
            "location": {"london", "british museum"},
            "area": {"british museum"},
            "venue_type": {"cafe", "coffee shop"},
            "max_radius_meters": 600,
            "proximity_location": {"british museum"},
        },
    },
    {
        "name": "new-york-kosher-deli-upper-west",
        "query": "Kosher delis on the Upper West Side of New York City.",
        "expected": {
            "location": {"new york", "new york city", "upper west side", "nyc"},
            "area": {"upper west side"},
            "dietary": {"kosher"},
            "venue_type": {"deli", "restaurant"},
        },
    },
    {
        "name": "los-angeles-tacos-boyle-heights",
        "query": "Mexican taco restaurants in Boyle Heights, Los Angeles.",
        "expected": {
            "location": {"los angeles", "boyle heights", "la"},
            "area": {"boyle heights"},
            "cuisine": {"mexican", "taco", "tacos"},
            "venue_type": {"restaurant", "taco restaurant"},
        },
    },
    {
        "name": "san-francisco-family-dim-sum",
        "query": "Family-friendly dim sum restaurants in San Francisco Chinatown.",
        "expected": {
            "location": {"san francisco", "chinatown"},
            "area": {"chinatown"},
            "cuisine": {"dim sum", "cantonese"},
            "venue_type": {"restaurant"},
            "group_fit": {
                "family friendly",
                "kid friendly",
                "children",
                "families",
            },
        },
    },
    {
        "name": "vancouver-budget-seafood-granville",
        "query": "Affordable seafood restaurants on Granville Island, Vancouver.",
        "expected": {
            "location": {"vancouver", "granville island"},
            "area": {"granville island"},
            "cuisine": {"seafood"},
            "venue_type": {"restaurant"},
            "price_style": {"affordable", "cheap", "budget", "inexpensive"},
        },
    },
    {
        "name": "auckland-maori-new-zealand-cuisine",
        "query": "Maori and New Zealand cuisine restaurants in Auckland.",
        "expected": {
            "location": {"auckland"},
            "cuisine": [{"maori"}, {"new zealand", "kiwi"}],
            "venue_type": {"restaurant"},
        },
    },
    {
        "name": "dublin-live-music-pubs-temple-bar",
        "query": "Live-music pubs in Temple Bar, Dublin.",
        "expected": {
            "location": {"dublin", "temple bar"},
            "area": {"temple bar"},
            "venue_type": [{"pub"}, {"live music"}],
        },
    },
    {
        "name": "brussels-chocolate-cafes-grand-place",
        "query": "Chocolate cafes and dessert shops near Grand Place in Brussels.",
        "expected": {
            "location": {"brussels", "grand place"},
            "area": {"grand place"},
            "venue_type": [
                {"cafe"},
                {"chocolate shop", "chocolatier", "dessert shop"},
            ],
        },
    },
]
