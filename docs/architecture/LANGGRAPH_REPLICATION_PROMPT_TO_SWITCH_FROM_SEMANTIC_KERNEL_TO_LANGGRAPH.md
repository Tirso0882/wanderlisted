# LangChain/LangGraph/LangSmith Replication Prompt

## Project Overview

You are building a **production-ready AI Travel Agent** web application. The original is built with Semantic Kernel + FastAPI + React. Your task is to replicate it using **LangChain**, **LangGraph**, and **LangSmith** as the AI stack, keeping the same architecture, capabilities, and external API integrations.

---

## Tech Stack — Original vs Target

| Layer | Original | Target (yours) |
|---|---|---|
| AI Framework | Semantic Kernel 1.0 | **LangChain + LangGraph** |
| LLM | Azure OpenAI GPT-4 | Azure OpenAI GPT-4 (same) |
| Observability | None | **LangSmith** (tracing + evals) |
| Backend | FastAPI (Python 3.11+) | FastAPI (Python 3.11+) — keep the same |
| Frontend | React 18 + TypeScript + Vite | React 18 + TypeScript + Vite — keep the same |
| Containerization | Docker + Docker Compose | Docker + Docker Compose — keep the same |

---

## Application Architecture

```
React Frontend (TypeScript + Vite)
        │  HTTP/REST
        ▼
FastAPI Backend (Python 3.11+)
        │
        ▼
LangGraph Agent  ←→  LangSmith (tracing)
        │
        ├── FlightSearchTool       → Amadeus API (OAuth2 sandbox)
        ├── FlightBookingTool      → Amadeus API
        ├── HotelSearchTool        → Amadeus API
        ├── WeatherTool            → OpenWeatherMap API (free tier)
        ├── CurrencyTool           → ExchangeRate-API (free tier)
        ├── ActivitySearchTool     → Foursquare API / static data
        ├── SafetyTool             → REST Countries API (free)
        ├── BudgetCalculatorTool   → Internal logic (no external API)
        └── IATALookupTool         → Internal dictionary (7,000+ airports)
```

---

## Agent Design — LangGraph ReAct Agent

### Core Pattern
Implement a **ReAct agent** using `langgraph.prebuilt.create_react_agent`. The agent must:
- Maintain **persistent conversation history** per session (keyed by `session_id` UUID).
- Automatically decide which tool(s) to call based on the user message.
- Use **Azure OpenAI** as the LLM via `langchain_openai.AzureChatOpenAI`.
- Be wrapped with **LangSmith tracing** via `@traceable` or project-level env vars.

### State Schema
```python
from langgraph.graph import MessagesState

class TravelAgentState(MessagesState):
    session_id: str
```

### Session Management
- Keep an in-memory dict `sessions: dict[str, list[BaseMessage]]` in Phase 1 (same as the original).
- Load existing messages into the graph state at the start of each turn.
- Save updated messages back after each turn.

---

## System Prompt

Use this exact system prompt for the agent:

```
You are an expert AI travel agent specializing in creating personalized, comprehensive travel itineraries.

Your responsibilities:
1. Understand traveler needs — ask clarifying questions about preferences, budget, interests, and travel dates.
2. Comprehensive planning — cover flights, hotels, activities, dining, budget, and logistics.
3. Personalization — tailor to travel style: adventure, relaxation, culture, luxury, or budget.
4. Practical advice — provide specific times, costs, and booking details.
5. Budget management — track all costs and suggest optimizations.
6. Safety & health — include travel advisories, visa requirements, health tips.

IMPORTANT — Tool Usage Rules:
- ALWAYS call flight search tools when users ask about flights. Accept city names OR IATA codes.
- ALWAYS call hotel search when users ask about accommodation.
- ALWAYS call weather tool to provide forecast for the destination dates.
- ALWAYS call currency tool when discussing costs in foreign currencies.
- ALWAYS call budget calculator to provide a cost summary for the full trip.
- ALWAYS call safety tool to include travel advisories for the destination country.
- Never claim you cannot access real-time data if a tool is available.

Response style: friendly, enthusiastic, professional. Use specific details (prices, times, names).
```

---

## Tools — Implementation Guide

Each tool is a `@tool`-decorated async function (LangChain `langchain_core.tools`). Mirror the original plugin logic exactly.

### 1. FlightSearchTool
- **Input**: `origin` (city name or IATA), `destination` (city name or IATA), `departure_date` (YYYY-MM-DD), `adults` (int), `return_date` (optional)
- **Logic**: 
  1. Call `IATALookupTool` internally to convert city names → IATA codes.
  2. Authenticate with Amadeus via OAuth2 (`POST /v1/security/oauth2/token`) using `client_credentials`.
  3. Call `GET /v2/shopping/flight-offers?originLocationCode=...`.
  4. Return top 5 results with price, airline, duration, stops.
- **Error handling**: catch 401 (bad credentials), 404 (no flights), network errors — return friendly message.

### 2. HotelSearchTool
- **Input**: `city_code` (IATA city code), `check_in_date`, `check_out_date`, `adults`
- **Logic**: Amadeus `GET /v1/reference-data/locations/hotels/by-city?cityCode=...` then `GET /v2/shopping/hotel-offers`.
- Returns: hotel name, stars, price per night, total price, amenities.

### 3. WeatherTool
- **Input**: `city` (string), `days` (int, 1–5)
- **Logic**: OpenWeatherMap `GET /data/2.5/forecast?q={city}&cnt={days*8}&units=metric`.
- Returns: daily high/low temp, precipitation, description per day.

### 4. CurrencyTool
- **Input**: `from_currency` (str), `to_currency` (str), `amount` (float)
- **Logic**: ExchangeRate-API `GET /v6/{api_key}/pair/{from}/{to}/{amount}`.
- Returns: converted amount, exchange rate, timestamp.

### 5. ActivitySearchTool
- **Input**: `city` (str), `category` (str, e.g. "sightseeing", "food", "outdoor"), `limit` (int)
- **Logic**: Foursquare Places API or curated static dataset per city.
- Returns: activity name, description, address, price range, rating.

### 6. SafetyTool
- **Input**: `country_name` (str)
- **Logic**: REST Countries API `GET /v3.1/name/{country}` for country metadata; optionally enrich with static advisory data.
- Returns: safety level, visa requirements, emergency numbers, health tips.

### 7. BudgetCalculatorTool
- **Input**: `destination_region` (str), `travel_style` ("budget" | "mid-range" | "luxury"), `duration_days` (int), `num_travelers` (int), `flight_cost` (float), `hotel_cost` (float)
- **Logic**: Pure Python. Use these daily cost baselines (USD):
  ```
  budget:    accommodation $30, meals $20, transport $10, activities $15, misc $10
  mid-range: accommodation $80, meals $40, transport $20, activities $30, misc $20
  luxury:    accommodation $200, meals $80, transport $40, activities $60, misc $40
  ```
  Apply regional multipliers (e.g. Western Europe ×1.3, East Asia ×0.9, South America ×0.65).
- Returns: itemized budget breakdown + total.

### 8. IATALookupTool
- **Input**: `location` (str) — city name, airport name, or IATA code
- **Logic**: Dictionary lookup of 7,000+ IATA codes. Accept fuzzy matching (lowercase, strip accents).
- Returns: IATA code string.

---

## FastAPI Endpoints

### `POST /api/v1/chat`
```python
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # auto-generated UUID if absent

class ChatResponse(BaseModel):
    message: str          # agent's reply (markdown)
    session_id: str
    itinerary: Optional[Itinerary] = None
```

### `GET /api/v1/health`
```python
{"status": "healthy", "version": "2.0.0", "framework": "langgraph"}
```

### CORS
Allow `http://localhost:3000` (frontend dev) + configurable origins via env var.

---

## LangSmith Integration

```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "travel-agent-specialist"
os.environ["LANGCHAIN_API_KEY"] = "<your-langsmith-key>"
```

- Every agent invocation is automatically traced.
- Tag each run with `session_id` and `user_message_length` as metadata.
- Create a LangSmith dataset from production traces for regression testing.

---

## Environment Variables

```env
# Azure OpenAI
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-01

# External APIs
AMADEUS_API_KEY=
AMADEUS_API_SECRET=
AMADEUS_BASE_URL=https://test.api.amadeus.com   # sandbox

OPENWEATHER_API_KEY=
EXCHANGERATE_API_KEY=
FOURSQUARE_API_KEY=

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=travel-agent-specialist
LANGCHAIN_API_KEY=

# App
FRONTEND_URL=http://localhost:3000
LOG_LEVEL=INFO
```

---

## Key Python Dependencies

```txt
# AI
langchain>=0.3
langchain-openai>=0.2
langchain-core>=0.3
langgraph>=0.2
langsmith>=0.2

# Backend
fastapi>=0.109
uvicorn[standard]>=0.27
pydantic>=2.5
httpx>=0.26
tenacity>=8.2

# Utilities
python-dotenv>=1.0
structlog>=24.1
```

---

## Behavior Requirements (Critical)

1. **Single agent, multiple tools** — do NOT create separate agents per feature. One LangGraph ReAct agent handles all intents.
2. **Context preservation** — the full `messages` list for a session is passed on every turn so the agent has memory.
3. **Tool chaining** — the agent must chain tools in one turn when needed (e.g., IATALookup → FlightSearch → CurrencyConversion → BudgetCalculator).
4. **Retry logic** — wrap Amadeus and other HTTP calls with `tenacity` (3 attempts, exponential backoff).
5. **Async** — all tools and the agent invocation must be `async`.
6. **Markdown responses** — the agent must respond in Markdown so the frontend can render it properly.
7. **Structured itinerary extraction** — after generating a full itinerary, also return a structured `Itinerary` Pydantic model parsed from the response (for the frontend itinerary view).

---

## Data Models

```python
class Flight(BaseModel):
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    duration: str
    price: float
    currency: str = "USD"
    stops: int = 0

class Hotel(BaseModel):
    name: str
    stars: int
    price_per_night: float
    total_price: float
    currency: str = "USD"
    address: str
    amenities: list[str] = []

class Activity(BaseModel):
    name: str
    description: str
    duration_hours: float
    price: float
    category: str

class DayPlan(BaseModel):
    day: int
    date: str
    activities: list[Activity]
    accommodation: Optional[Hotel]
    meals_budget: float
    notes: str

class Itinerary(BaseModel):
    destination: str
    duration_days: int
    travel_style: str
    total_budget: float
    currency: str
    flights: list[Flight]
    days: list[DayPlan]
    budget_breakdown: dict[str, float]
```

---

## LangGraph Agent Skeleton

```python
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

llm = AzureChatOpenAI(
    azure_deployment=settings.azure_openai_deployment_name,
    azure_endpoint=settings.azure_openai_endpoint,
    api_key=settings.azure_openai_api_key,
    api_version=settings.azure_openai_api_version,
    temperature=0.7,
)

tools = [
    flight_search_tool,
    flight_booking_tool,
    hotel_search_tool,
    weather_tool,
    currency_tool,
    activity_search_tool,
    safety_tool,
    budget_calculator_tool,
    iata_lookup_tool,
]

agent = create_react_agent(
    model=llm,
    tools=tools,
    state_modifier=TRAVEL_AGENT_SYSTEM_PROMPT,
)

@traceable(project_name="travel-agent-specialist")
async def run_agent(message: str, session_id: str) -> str:
    history = sessions.get(session_id, [])
    input_messages = history + [HumanMessage(content=message)]
    result = await agent.ainvoke({"messages": input_messages})
    sessions[session_id] = result["messages"]
    return result["messages"][-1].content
```

---

## Out of Scope for Phase 1 (replicate as-is from original)

- Redis session store (use in-memory dict for now)
- OAuth2/JWT user authentication (use a passthrough `get_current_user` dependency)
- Terraform / cloud infrastructure
- Interactive maps on the frontend
- Multi-destination planning beyond what the agent naturally handles

---

## Summary

Build this as a clean LangGraph ReAct agent replacing Semantic Kernel, keeping all external API integrations and the FastAPI + React shell identical. Instrument everything with LangSmith from day one. Follow async patterns throughout. The agent's tool-calling behavior should be functionally identical to the original — the LLM decides which tools to invoke based on the user's natural language request.
