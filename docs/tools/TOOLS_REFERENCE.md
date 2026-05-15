# Tools Reference

> Quick-reference catalog of all 20 tools across 13 modules.

---

## Tool Catalog

### Flight & Airport Tools

| Tool | Module | Description | Parameters | API |
|------|--------|-------------|------------|-----|
| `lookup_iata_code` | `iata.py` | Look up the IATA airport code for a city, airport name, or IATA code. | `location` | Local CSV (~7,700 airports, fuzzy match) |
| `search_flights` | `flights.py` | Search for flights between two airports. Returns top 5 options with price, airline, duration, stops. | `origin`, `destination`, `departure_date`, `adults=1`, `return_date=""` | Amadeus Flight Offers v2 |

### Hotel Tools

| Tool | Module | Description | Parameters | API |
|------|--------|-------------|------------|-----|
| `search_hotels` | `hotels.py` | Search for hotels in a city with real pricing via Amadeus. | `city_code`, `check_in_date`, `check_out_date`, `adults=1` | Amadeus Hotel v1/v3 |
| `search_hotels_hotelbeds` | `hotels_hotelbeds.py` | Search 250K+ hotels (strong on independents/boutique). Supports children, ratings, filters. | `city_code`, `check_in_date`, `check_out_date`, `adults=2`, `children=0`, `children_ages=""`, `min_category=None`, `max_rate=None`, `board_codes=""` | Hotelbeds Booking API |
| `check_hotel_rate_hotelbeds` | `hotels_hotelbeds.py` | Verify current price and get detailed rate breakdown for a Hotelbeds room. | `rate_keys`, `include_upselling=False` | Hotelbeds Booking API |

### Location & Maps Tools

| Tool | Module | Description | Parameters | API |
|------|--------|-------------|------------|-----|
| `search_places_nearby` | `google_maps.py` | Search for places near a location by type. | `location`, `place_type`, `radius_meters=1500`, `max_results=10` | Google Places (New) |
| `search_places_text` | `google_maps.py` | Free-text place search via Google Places. | `query`, `max_results=10` | Google Places (New) |
| `get_directions` | `google_maps.py` | Get directions between two points (modes: transit, driving, walking, bicycling). | `origin`, `destination`, `mode="transit"`, `departure_time=None` | Google Directions |
| `get_distance_matrix` | `google_maps.py` | Travel distances and durations between multiple origins and destinations. | `origins`, `destinations`, `mode="driving"` | Google Distance Matrix |
| `compute_route` | `google_maps.py` | Compute an optimised route with optional waypoints. | `origin`, `destination`, `travel_mode="DRIVE"`, `waypoints=None` | Google Routes |
| `optimize_day_route` | `google_maps.py` | Optimize the order of stops for a day trip. | `stops`, `start_location`, `end_location=None`, `travel_mode="DRIVE"` | Google Routes |
| `get_timezone` | `google_maps.py` | Get timezone information for a location. | `location`, `timestamp=None` | Google Time Zone |

### Research & Knowledge Tools

| Tool | Module | Description | Parameters | API |
|------|--------|-------------|------------|-----|
| `search_destination_guides` | `destination_rag.py` | Search curated destination guides (Pinecone RAG) for local tips and cultural context. | `query`, `destinations=None`, `top_k=5`, `tenant=None` | Pinecone |
| `research_destination` | `destination_research.py` | Hybrid: curated guides + live web search + Cohere reranking. | `query`, `destinations=None`, `tenant=None` | Pinecone + Tavily + Cohere |
| `search_web` | `web_search.py` | Real-time web search for travel information. | `query`, `destinations=None`, `topic="general"` | Tavily |
| `search_hidden_gems` | `web_search.py` | Search for hidden gems, local favorites, off-the-beaten-path experiences. | `destination`, `interests=None` | Tavily |
| `search_activities` | `activities.py` | Search for activities, attractions, and restaurants in a city. | `city`, `category="sightseeing"`, `query=""`, `limit=5` | Google Places (New) |

### Weather, Budget & Utility Tools

| Tool | Module | Description | Parameters | API |
|------|--------|-------------|------------|-----|
| `get_weather` | `weather.py` | Get weather forecast for a city (1–5 days). | `city`, `days=5` | OpenWeatherMap |
| `convert_currency` | `currency.py` | Convert an amount between currencies using live exchange rates. | `from_currency`, `to_currency`, `amount` | ExchangeRate API |
| `calculate_budget` | `budget.py` | Calculate an estimated trip budget with itemized breakdown. | `destination_region`, `travel_style="mid-range"`, `duration_days=7`, `num_travelers=1`, `flight_cost=0`, `hotel_cost=0` | None (computation) |
| `get_safety_info` | `safety.py` | Get travel safety and general information for a country. | `country_name` | REST Countries |

---

## Agent → Tool Mapping

| Agent | Tools |
|-------|-------|
| **FlightsAgent** | `lookup_iata_code`, `search_flights` |
| **HotelsAgent** | `search_hotels`, `search_hotels_hotelbeds`, `check_hotel_rate_hotelbeds`, `search_activities`, `search_places_text` |
| **DestinationAgent** | `research_destination`, `search_destination_guides`, `search_web`, `search_hidden_gems`, `get_weather`, `get_safety_info`, `get_timezone` |
| **RestaurantsAgent** | `search_places_nearby`, `search_places_text` |
| **ActivitiesAgent** | `search_places_nearby`, `search_places_text` |
| **TransportationAgent** | `get_directions`, `get_distance_matrix`, `compute_route` |
| **BudgetAgent** | `calculate_budget`, `convert_currency` |
| **ItineraryAgent** | `optimize_day_route`, `get_distance_matrix` |
| **SupervisorAgent** | *(none — coordination only)* |

---

## Environment Variables

All API credentials are loaded from environment variables. Required variables for full functionality:

```bash
# LLM
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=

# Flights & Hotels (Amadeus)
AMADEUS_API_KEY=
AMADEUS_API_SECRET=

# Hotels (Hotelbeds)
HOTELBEDS_API_KEY=
HOTELBEDS_SECRET=

# Google Maps Platform (Places, Directions, Routes, Timezone)
GOOGLE_MAPS_API_KEY=

# Weather
OPENWEATHERMAP_API_KEY=

# Currency
EXCHANGE_RATE_API_KEY=

# Web Search
TAVILY_API_KEY=

# RAG
PINECONE_API_KEY=

# Reranking (optional)
COHERE_API_KEY=

# LangSmith tracing (optional)
LANGSMITH_API_KEY=
LANGCHAIN_TRACING_V2=true
```
