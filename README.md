# Wanderlisted

AI-powered travel itinerary planner built with LangGraph, LangChain, and Azure OpenAI. Generates comprehensive, personalized travel itineraries with real-time data from flights, hotels, weather, activities, and budget APIs.

## Architecture

```
User → FastAPI (/api/v1/chat) → ReAct Agent (LangGraph)
                                      │
                         ┌────────────┼────────────────┐
                         ▼            ▼                ▼
                    9 Tools      Azure OpenAI      LangSmith
                  (see below)     (GPT-4)         (tracing)
                      │
                      └── RAG (Pinecone + text-embedding-3-large)
                            └── knowledge_base/destination_guides/
```

**Current stage:** Stage 3 — RAG Knowledge Base

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | LangGraph + LangChain |
| LLM | Azure OpenAI (GPT-4) |
| API server | FastAPI + Uvicorn |
| Observability | LangSmith tracing |
| HTTP client | httpx (async) |
| Retry logic | tenacity (exponential backoff) |
| Data validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio + respx |
| Vector store | Pinecone (serverless) |
| Embeddings | Azure OpenAI text-embedding-3-large |
| Text splitting | langchain-experimental (SemanticChunker) |
| Python | 3.12+ |

## Tools

| Tool | API | Purpose |
|------|-----|---------|
| `lookup_iata_code` | Offline (CSV) | Resolve city names to airport codes (7,700+ airports) |
| `calculate_budget` | Offline | Itemized trip budget with regional baselines |
| `get_weather` | OpenWeatherMap | 5-day weather forecast |
| `convert_currency` | ExchangeRate API | Live currency conversion |
| `get_safety_info` | REST Countries | Country info, languages, currency, travel notes |
| `search_flights` | Amadeus | Flight search with pricing |
| `search_hotels` | Amadeus | Hotel search with real pricing |
| `search_activities` | Google Places (New) | Activities, restaurants, attractions with photos and maps |
| `search_destination_guides` | RAG (Pinecone) | Local tips, cultural context, hidden gems from curated guides |

## Quick Start

### Prerequisites

- Python 3.12+
- API keys (see [Environment Variables](#environment-variables))

### Setup

```bash
# Clone and enter the project
git clone <repo-url> && cd wanderlisted

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy environment template and fill in your keys
cp .env.example .env
# Edit .env with your actual API keys
```

### Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Source |
|----------|----------|--------|
| `AZURE_OPENAI_API_KEY` | Yes | [Azure Portal](https://portal.azure.com) |
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure Portal → OpenAI resource → Keys |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Yes | Azure Portal → OpenAI → Deployments |
| `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` | Yes | Azure Portal → OpenAI → Deployments (use `text-embedding-3-large`) |
| `PINECONE_API_KEY` | Yes | [Pinecone Console](https://app.pinecone.io) |
| `OPENWEATHER_API_KEY` | Yes | [OpenWeatherMap](https://openweathermap.org/api) |
| `EXCHANGERATE_API_KEY` | Yes | [ExchangeRate API](https://www.exchangerate-api.com/) |
| `AMADEUS_API_KEY` | Yes | [Amadeus for Developers](https://developers.amadeus.com/) |
| `AMADEUS_API_SECRET` | Yes | Amadeus developer dashboard |
| `GOOGLE_MAPS_API_KEY` | Yes | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |
| `LANGCHAIN_API_KEY` | Yes | [LangSmith](https://smith.langchain.com/) |

### Run the Server

```bash
# Development (with auto-reload)
uvicorn src.api.main:app --reload

# Test chat endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather in Tokyo?"}'
```

### Run with LangGraph Studio

```bash
langgraph dev
```

Open the Studio UI at the URL shown in the terminal output.

## Testing

The project uses pytest with two test tiers:

- **Unit tests** — mock all external APIs via respx, run instantly, no keys needed
- **Integration tests** — call live APIs, auto-skipped when keys are missing

```bash
# Run unit tests only (fast, no API keys needed)
pytest tests/ -m "not integration"

# Run all tests including live API calls
pytest tests/ -m ""

# Run with coverage report
pytest tests/ -m "not integration" --cov --cov-report=term-missing

# Run a specific test file
pytest tests/test_iata.py -v
```

### Test Structure

```
tests/
├── conftest.py            # Shared fixtures, API key detection
├── test_iata.py           # IATA lookup: direct, substring, fuzzy, edge cases
├── test_budget.py         # Budget calculator: regions, styles, scaling
├── test_weather.py        # Weather: mocked OpenWeatherMap responses
├── test_currency.py       # Currency: mocked ExchangeRate responses
├── test_safety.py         # Safety: mocked REST Countries responses
├── test_flights.py        # Flights: mocked Amadeus OAuth + search
├── test_hotels.py         # Hotels: mocked Amadeus two-step search
├── test_activities.py     # Activities: mocked Google Places responses
├── test_indexer.py         # RAG indexer: hashing, staleness, chunking, build/cache
├── test_destination_rag.py # RAG tool: search, no guides, lazy init
├── test_models.py         # Pydantic models: validation, defaults, roundtrip
└── test_integration.py    # Live API tests (auto-skipped without keys)
```

## Project Structure

```
wanderlisted/
├── src/
│   ├── agent/
│   │   ├── agent.py              # Agent factory (create_agent + checkpointer)
│   │   ├── graph.py              # LangGraph Studio entrypoint
│   │   ├── state.py              # TravelAgentState schema
│   │   └── prompts/
│   │       ├── __init__.py
│   │       └── agent_prompt.py   # System prompt + specialized prompts
│   ├── api/
│   │   └── main.py               # FastAPI app with /chat and /health
│   ├── data/
│   │   └── iata_codes.csv        # 7,700 airport codes
│   ├── models/
│   │   └── __init__.py           # Pydantic models (Flight, Hotel, Itinerary, etc.)
│   ├── rag/
│   │   ├── __init__.py
│   │   └── indexer.py            # Pinecone index builder with staleness detection
│   └── tools/
│       ├── activities.py         # Google Places API (New)
│       ├── budget.py             # Pure Python budget calculator
│       ├── currency.py           # ExchangeRate API
│       ├── destination_rag.py    # RAG-powered destination guide search
│       ├── flights.py            # Amadeus Flight Offers API
│       ├── hotels.py             # Amadeus Hotel API
│       ├── iata.py               # CSV-backed IATA lookup with fuzzy matching
│       ├── safety.py             # REST Countries API
│       └── weather.py            # OpenWeatherMap API
├── knowledge_base/
│   ├── destination_guides/       # Wikivoyage travel guides (RAG source)
│   └── .cache/                   # Manifest only (index lives in Pinecone)
├── scripts/
│   └── download_guides.py        # Wikivoyage downloader
├── tests/                        # pytest suite (unit + integration)
├── docs/                         # Reference documentation
├── outputs/                      # Generated itineraries
├── .env.example                  # Environment variable template
├── langgraph.json                # LangGraph Studio config
├── pyproject.toml                # Project metadata + pytest config
├── requirements.txt              # Python dependencies
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/chat` | Send a message to the travel agent |
| `GET` | `/api/v1/health` | Health check |

### POST /api/v1/chat

```json
// Request
{
  "message": "Plan a 5-day trip to Tokyo from Seattle, budget $3000",
  "session_id": "optional-uuid-for-conversation-continuity"
}

// Response
{
  "message": "Here's your Tokyo itinerary...",
  "session_id": "generated-or-provided-uuid"
}
```

## Development Roadmap

- [x] **Stage 1** — Single ReAct agent + LangSmith tracing
- [x] **Stage 2** — Full 8-tool suite + Pydantic models + pytest
- [x] **Stage 3** — RAG knowledge base (destination guides)
- [ ] **Stage 4** — Multi-agent architecture (supervisor + specialists)
- [ ] **Stage 5** — Shallow/deep routing + YAML config
- [ ] **Stage 6** — LangSmith evaluation suite
- [ ] **Stage 7** — Enhanced HTML output (photos, maps, routes)

## License

See [LICENSE](LICENSE).
