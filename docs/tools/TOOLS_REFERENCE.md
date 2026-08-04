# Tools Reference

> Quick-reference catalog of the active tool adapters.

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
| `compute_route` | `google_maps.py` | Directions (with turn-by-turn/transit steps) and multi-stop routes with waypoint optimisation. | `origin`, `destination`, `travel_mode="DRIVE"`, `waypoints=None`, `include_steps=True` | Google Routes |
| `optimize_day_route` | `google_maps.py` | Optimize the order of stops for a day trip. | `stops`, `start_location`, `end_location=None`, `travel_mode="DRIVE"` | Google Routes |
| `get_timezone` | `google_maps.py` | Get timezone information for a location. | `location`, `timestamp=None` | Google Time Zone |

### Destination Research

| Tool | Module | Description | Parameters | API |
|------|--------|-------------|------------|-----|
| `search_destination_web` | `web_search.py` | Return normalized Tavily evidence through the shared provider for the legacy graph. | `query`, `topic="overview"`, `max_results=5` | Tavily |
| `search_activities` | `activities.py` | Search for activities, attractions, and restaurants in a city. | `city`, `category="sightseeing"`, `query=""`, `limit=5` | Google Places (New) |

### Budget & Utility Tools

| Tool | Module | Description | Parameters | API |
|------|--------|-------------|------------|-----|
| `convert_currency` | `currency.py` | Convert an amount between currencies using live exchange rates. | `from_currency`, `to_currency`, `amount` | ExchangeRate API |
| `calculate_budget` | `budget.py` | Calculate an estimated trip budget with itemized breakdown. | `destination_region`, `travel_style="mid-range"`, `duration_days=7`, `num_travelers=1`, `flight_cost=0`, `hotel_cost=0` | None (computation) |

---

## Agent → Tool Mapping

| Agent | Tools |
|-------|-------|
| **FlightsAgent** | `lookup_iata_code`, `search_flights` |
| **HotelsAgent** | `search_hotels`, `search_hotels_hotelbeds`, `check_hotel_rate_hotelbeds`, `search_activities`, `search_places_text` |
| **TravelReadinessAgent** | Fixed Tavily + Open-Meteo pipeline (`src/readiness/`, compatibility implementation in `src/destination/`), not a ReAct tool loop |
| **RestaurantsAgent** | `search_places_nearby`, `search_places_text` |
| **ActivitiesAgent** | `search_places_nearby`, `search_places_text` |
| **TransportationAgent** | `compute_route` |
| **BudgetAgent** | `calculate_budget`, `convert_currency` |
| **ItineraryAgent** | `optimize_day_route` |
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

# Currency
EXCHANGE_RATE_API_KEY=

# Web Search
TAVILY_API_KEY=

# LangSmith tracing (optional)
LANGSMITH_API_KEY=
LANGCHAIN_TRACING_V2=true
```
