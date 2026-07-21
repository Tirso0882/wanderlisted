"""Golden decision dataset for ActivitiesAgent Google Places searches.

Each item follows the component EDD schema shared by the completed agents:
``name``, ``tags``, ``query``, and a task-grounded ``expected`` mapping.
Only constraints stated by the traveler are labeled. A list of sets represents
required concept groups; terms inside one set are acceptable alternatives.
``locations`` is deliberately a list so multi-city requests require coverage of
every requested city rather than allowing the first city to satisfy the case.
"""

from __future__ import annotations

DATASET_VERSION = "1.0.0"
DATASET_SIZE = 40

DATASET: list[dict] = [
    {
        "name": "paris-art-museums",
        "tags": ["baseline", "museum", "art"],
        "query": "Find art museums and galleries to visit in Paris.",
        "expected": {
            "locations": [{"paris"}],
            "interests": [{"art", "art history"}],
            "activity_type": [{"museum", "gallery"}],
        },
    },
    {
        "name": "kyoto-temples-gion",
        "tags": ["baseline", "culture", "neighborhood"],
        "query": "Recommend temples and traditional cultural experiences around Gion in Kyoto.",
        "expected": {
            "locations": [{"kyoto", "gion"}],
            "interests": [{"temple", "traditional culture", "cultural"}],
            "activity_type": [{"temple", "tourist attraction"}],
        },
    },
    {
        "name": "rome-ancient-history",
        "tags": ["history", "landmarks"],
        "query": "What ancient Roman history sites and landmarks should I see in Rome?",
        "expected": {
            "locations": [{"rome"}],
            "interests": [{"ancient roman", "history"}],
            "activity_type": [{"landmark", "tourist attraction", "museum"}],
        },
    },
    {
        "name": "new-york-family-central-park",
        "tags": ["family", "outdoors", "parks"],
        "query": "Suggest kid-friendly outdoor activities near Central Park in New York City.",
        "expected": {
            "locations": [{"new york city", "new york", "central park", "nyc"}],
            "interests": [{"outdoor", "park"}],
            "activity_type": [{"park", "tourist attraction"}],
            "group_fit": [{"kid friendly", "family friendly", "children", "kids"}],
        },
    },
    {
        "name": "london-wheelchair-museums",
        "tags": ["accessibility", "museum"],
        "query": "Find wheelchair-accessible museums in central London.",
        "expected": {
            "locations": [{"london", "central london"}],
            "activity_type": [{"museum"}],
            "accessibility": [{"wheelchair accessible", "wheelchair access"}],
        },
    },
    {
        "name": "barcelona-sagrada-radius",
        "tags": ["proximity", "landmarks"],
        "query": "Find attractions within 800 metres of Sagrada Familia in Barcelona.",
        "expected": {
            "locations": [{"barcelona", "sagrada familia"}],
            "activity_type": [{"tourist attraction", "landmark"}],
            "max_radius_meters": 800,
            "proximity_location": {"sagrada familia"},
        },
    },
    {
        "name": "tokyo-anime-akihabara",
        "tags": ["interests", "neighborhood"],
        "query": "I love anime and gaming. Find activities and places to explore in Akihabara, Tokyo.",
        "expected": {
            "locations": [{"tokyo", "akihabara"}],
            "interests": [{"anime", "gaming", "video game"}],
            "activity_type": [{"tourist attraction", "museum", "store"}],
        },
    },
    {
        "name": "berlin-kreuzberg-nightlife",
        "tags": ["nightlife", "neighborhood"],
        "query": "Recommend nightlife and live music venues in Kreuzberg, Berlin.",
        "expected": {
            "locations": [{"berlin", "kreuzberg"}],
            "interests": [{"nightlife", "live music"}],
            "activity_type": [{"night club", "bar", "live music venue"}],
        },
    },
    {
        "name": "cape-town-hiking",
        "tags": ["outdoors", "nature"],
        "query": "Find scenic hikes and outdoor nature experiences in Cape Town.",
        "expected": {
            "locations": [{"cape town"}],
            "interests": [{"hike", "hiking", "outdoor", "nature"}],
            "activity_type": [{"park", "tourist attraction"}],
        },
    },
    {
        "name": "amsterdam-canals-art",
        "tags": ["culture", "waterfront"],
        "query": "Recommend canal experiences and art museums in Amsterdam.",
        "expected": {
            "locations": [{"amsterdam"}],
            "interests": [{"canal"}, {"art"}],
            "activity_type": [{"museum", "tourist attraction"}],
        },
    },
    {
        "name": "istanbul-bazaars-markets",
        "tags": ["markets", "culture"],
        "query": "Find bazaars, markets, and local cultural experiences in Istanbul.",
        "expected": {
            "locations": [{"istanbul"}],
            "interests": [{"bazaar", "market"}, {"cultural", "local"}],
            "activity_type": [{"market", "tourist attraction"}],
        },
    },
    {
        "name": "marrakech-hammam",
        "tags": ["wellness", "culture"],
        "query": "Recommend a traditional hammam and wellness experiences in Marrakech.",
        "expected": {
            "locations": [{"marrakech"}],
            "interests": [{"hammam", "wellness", "spa"}],
            "activity_type": [{"spa", "tourist attraction"}],
        },
    },
    {
        "name": "reykjavik-northern-lights",
        "tags": ["seasonal", "nature"],
        "query": "Find northern lights tours and winter experiences from Reykjavik in February.",
        "expected": {
            "locations": [{"reykjavik"}],
            "interests": [{"northern lights", "aurora"}, {"winter"}],
            "activity_type": [{"tourist attraction", "tour operator"}],
        },
    },
    {
        "name": "lisbon-fado-alfama",
        "tags": ["music", "neighborhood"],
        "query": "Find authentic fado music experiences in Alfama, Lisbon.",
        "expected": {
            "locations": [{"lisbon", "alfama"}],
            "interests": [{"fado"}, {"music", "live music"}],
            "activity_type": [{"live music venue", "bar", "tourist attraction"}],
        },
    },
    {
        "name": "rio-samba",
        "tags": ["music", "nightlife"],
        "query": "Find samba music and dance experiences in Rio de Janeiro.",
        "expected": {
            "locations": [{"rio de janeiro", "rio"}],
            "interests": [{"samba"}, {"music", "dance"}],
            "activity_type": [{"night club", "live music venue", "tourist attraction"}],
        },
    },
    {
        "name": "bangkok-cooking-class",
        "tags": ["food", "classes"],
        "query": "Find Thai cooking classes and food experiences in Bangkok.",
        "expected": {
            "locations": [{"bangkok"}],
            "interests": [{"thai cooking", "cooking class"}, {"food"}],
            "activity_type": [{"tourist attraction", "school"}],
        },
    },
    {
        "name": "buenos-aires-tango",
        "tags": ["music", "culture"],
        "query": "Recommend tango shows and dance experiences in Buenos Aires.",
        "expected": {
            "locations": [{"buenos aires"}],
            "interests": [{"tango"}, {"dance"}],
            "activity_type": [{"live music venue", "night club", "tourist attraction"}],
        },
    },
    {
        "name": "new-orleans-jazz",
        "tags": ["music", "nightlife"],
        "query": "Find jazz clubs and live music activities in New Orleans.",
        "expected": {
            "locations": [{"new orleans"}],
            "interests": [{"jazz"}, {"live music"}],
            "activity_type": [{"live music venue", "bar", "night club"}],
        },
    },
    {
        "name": "venice-limited-mobility",
        "tags": ["accessibility", "culture"],
        "query": "Suggest limited-mobility-friendly attractions and museums in Venice.",
        "expected": {
            "locations": [{"venice"}],
            "activity_type": [{"museum", "tourist attraction"}],
            "accessibility": [{"limited mobility", "accessible", "wheelchair"}],
        },
    },
    {
        "name": "singapore-family-science",
        "tags": ["family", "museum"],
        "query": "Find child-friendly science and interactive museum activities in Singapore.",
        "expected": {
            "locations": [{"singapore"}],
            "interests": [{"science", "interactive"}],
            "activity_type": [{"museum", "tourist attraction"}],
            "group_fit": [{"child friendly", "kid friendly", "family friendly", "children"}],
        },
    },
    {
        "name": "reykjavik-budget-free",
        "tags": ["travel-style", "budget", "nature"],
        "query": "Show me free or budget-friendly outdoor things to do in Reykjavik.",
        "expected": {
            "locations": [{"reykjavik"}],
            "interests": [{"outdoor", "nature"}],
            "activity_type": [{"park", "tourist attraction"}],
            "travel_style": [{"free", "budget", "low cost", "affordable"}],
        },
    },
    {
        "name": "dubai-luxury-experiences",
        "tags": ["travel-style", "luxury"],
        "query": "Recommend luxury and VIP experiences in Dubai.",
        "expected": {
            "locations": [{"dubai"}],
            "interests": [{"luxury", "vip", "exclusive"}],
            "activity_type": [{"tourist attraction", "spa"}],
            "travel_style": [{"luxury", "vip", "exclusive"}],
        },
    },
    {
        "name": "seoul-k-pop",
        "tags": ["interests", "culture"],
        "query": "Find K-pop and contemporary Korean culture activities in Seoul.",
        "expected": {
            "locations": [{"seoul"}],
            "interests": [{"k pop", "korean pop"}, {"korean culture", "contemporary korean"}],
            "activity_type": [{"tourist attraction", "live music venue", "museum"}],
        },
    },
    {
        "name": "tokyo-osaka-multicity",
        "tags": ["multi-city", "culture"],
        "query": "Plan cultural activities in both Tokyo and Osaka, with museums in Tokyo and food markets in Osaka.",
        "expected": {
            "locations": [{"tokyo"}, {"osaka"}],
            "interests": [{"museum"}, {"food market", "market"}],
            "activity_type": [{"museum", "market", "tourist attraction"}],
        },
    },
    {
        "name": "rome-florence-multicity",
        "tags": ["multi-city", "art", "history"],
        "query": "Find art and history activities for both Rome and Florence.",
        "expected": {
            "locations": [{"rome"}, {"florence"}],
            "interests": [{"art"}, {"history"}],
            "activity_type": [{"museum", "tourist attraction"}],
        },
    },
    {
        "name": "kyoto-nara-multicity",
        "tags": ["multi-city", "culture"],
        "query": "Recommend temples and heritage activities in Kyoto and Nara.",
        "expected": {
            "locations": [{"kyoto"}, {"nara"}],
            "interests": [{"temple"}, {"heritage", "cultural"}],
            "activity_type": [{"temple", "tourist attraction"}],
        },
    },
    {
        "name": "barcelona-dance-studio-rental",
        "tags": ["venue-rental", "dance", "group"],
        "query": "Find an hourly dance studio room rental in Barcelona for a group rehearsal.",
        "expected": {
            "locations": [{"barcelona"}],
            "interests": [{"dance"}, {"rehearsal"}],
            "activity_type": [{"dance studio", "studio"}],
            "group_fit": [{"group", "rehearsal"}],
            "venue_rental": [{"room rental", "studio rental", "hourly"}],
        },
    },
    {
        "name": "warsaw-dance-room-rental",
        "tags": ["venue-rental", "multilingual", "dance"],
        "query": "Znajdz sale do tanca na wynajem na godziny w Warszawie.",
        "expected": {
            "locations": [{"warsaw", "warszawa"}],
            "interests": [{"dance", "tanca"}],
            "activity_type": [{"dance studio", "studio"}],
            "venue_rental": [{"rental", "wynajem", "hourly", "godziny"}],
        },
    },
    {
        "name": "london-rehearsal-room-rental",
        "tags": ["venue-rental", "music"],
        "query": "Find a rehearsal room to rent by the hour in London for a small band.",
        "expected": {
            "locations": [{"london"}],
            "interests": [{"rehearsal"}, {"band", "music"}],
            "activity_type": [{"studio", "rehearsal studio"}],
            "venue_rental": [{"room rental", "rent", "hourly"}],
        },
    },
    {
        "name": "berlin-workshop-space-rental",
        "tags": ["venue-rental", "workshop"],
        "query": "Find a workshop or event space to rent for one day in Berlin.",
        "expected": {
            "locations": [{"berlin"}],
            "interests": [{"workshop"}, {"event"}],
            "activity_type": [{"event venue", "event space", "conference center"}],
            "venue_rental": [{"rent", "rental", "one day", "day hire"}],
        },
    },
    {
        "name": "prague-large-group-event-space",
        "tags": ["venue-rental", "group"],
        "query": "Find an event room rental in Prague for a workshop with 20 people.",
        "expected": {
            "locations": [{"prague"}],
            "interests": [{"workshop"}, {"event room", "event space"}],
            "activity_type": [{"event venue", "conference center", "event space"}],
            "group_fit": [{"20 people", "large group", "group"}],
            "venue_rental": [{"rental", "rent", "hire"}],
        },
    },
    {
        "name": "florence-wheelchair-art",
        "tags": ["accessibility", "art"],
        "query": "Find wheelchair-accessible art museums and galleries in Florence.",
        "expected": {
            "locations": [{"florence"}],
            "interests": [{"art"}],
            "activity_type": [{"museum", "gallery"}],
            "accessibility": [{"wheelchair accessible", "wheelchair access"}],
        },
    },
    {
        "name": "madrid-accessible-prado-radius",
        "tags": ["accessibility", "proximity", "museum", "multilingual"],
        "query": "Busca museos accesibles a menos de 600 metros del Museo del Prado en Madrid.",
        "expected": {
            "locations": [{"madrid", "museo del prado", "prado museum"}],
            "activity_type": [{"museum"}],
            "accessibility": [{"accesibles", "accessible", "wheelchair"}],
            "max_radius_meters": 600,
            "proximity_location": {"museo del prado", "prado museum"},
        },
    },
    {
        "name": "paris-free-family",
        "tags": ["family", "travel-style", "budget"],
        "query": "Find free family-friendly activities in Paris for two children.",
        "expected": {
            "locations": [{"paris"}],
            "activity_type": [{"park", "museum", "tourist attraction"}],
            "group_fit": [{"family friendly", "kid friendly", "children", "kids"}],
            "travel_style": [{"free", "budget", "low cost"}],
        },
    },
    {
        "name": "nice-french-children",
        "tags": ["family", "multilingual", "beaches"],
        "query": "Quelles activites adaptees aux enfants recommandez-vous a Nice?",
        "expected": {
            "locations": [{"nice"}],
            "activity_type": [{"park", "tourist attraction", "museum"}],
            "group_fit": [{"enfants", "child friendly", "kid friendly", "family friendly"}],
        },
    },
    {
        "name": "munich-christmas-markets",
        "tags": ["seasonal", "markets"],
        "query": "Find Christmas markets and winter activities in Munich in December.",
        "expected": {
            "locations": [{"munich"}],
            "interests": [{"christmas market"}, {"winter"}],
            "activity_type": [{"market", "tourist attraction"}],
        },
    },
    {
        "name": "nairobi-wildlife",
        "tags": ["nature", "wildlife"],
        "query": "Recommend wildlife and nature experiences in Nairobi.",
        "expected": {
            "locations": [{"nairobi"}],
            "interests": [{"wildlife"}, {"nature"}],
            "activity_type": [{"zoo", "park", "tourist attraction"}],
        },
    },
    {
        "name": "mexico-city-frida-kahlo-radius",
        "tags": ["proximity", "art", "history"],
        "query": "Find art and history attractions within 1000 metres of the Frida Kahlo Museum in Mexico City.",
        "expected": {
            "locations": [{"mexico city", "frida kahlo museum"}],
            "interests": [{"art"}, {"history"}],
            "activity_type": [{"museum", "tourist attraction"}],
            "max_radius_meters": 1000,
            "proximity_location": {"frida kahlo museum"},
        },
    },
    {
        "name": "vancouver-luxury-wellness",
        "tags": ["travel-style", "luxury", "wellness"],
        "query": "Recommend luxury spa and wellness experiences in Vancouver.",
        "expected": {
            "locations": [{"vancouver"}],
            "interests": [{"spa"}, {"wellness"}],
            "activity_type": [{"spa", "tourist attraction"}],
            "travel_style": [{"luxury", "exclusive", "vip"}],
        },
    },
    {
        "name": "dublin-large-group-games",
        "tags": ["group", "family", "games"],
        "query": "Find group activities for 12 people, such as escape rooms or games, in Dublin.",
        "expected": {
            "locations": [{"dublin"}],
            "interests": [{"escape room", "games"}],
            "activity_type": [{"amusement center", "tourist attraction"}],
            "group_fit": [{"12 people", "large group", "group"}],
        },
    },
]
