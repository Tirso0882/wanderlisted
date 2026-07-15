# Wanderlisted — Copilot Instructions

## Project Overview
Wanderlisted is a **multi-agent AI travel itinerary planner** (v0.2.0) built with Python 3.12+, LangChain, LangGraph, and LangSmith. It uses a **supervisor-routed architecture** where 10 specialized agents (Supervisor, Flights, Hotels, Destination, Restaurants, Activities, Transportation, Budget, Itinerary) fan out in parallel to produce personalized travel itineraries. The system includes a **Next.js 16 frontend**, **FastAPI backend** with SSE streaming, **MCP server** for external AI agents, and a **four-layer evaluation framework**.

## Project Structure

### Backend (Python)
- `src/agent/` — LangGraph graphs, agent definitions, state, prompts, rendering
  - `src/agent/agents/` — 10 specialized agents (one file each, extends `SpecializedAgent`)
  - `src/agent/prompts/` — 16 system prompts in `agent_prompt.py`, exported via `__init__.py`
  - `src/agent/templates/` — Jinja2 templates (`handbook_template.html.j2`)
  - `src/agent/stage4_graph.py` — **Primary graph**: multi-agent supervisor with parallel fan-out (1500+ lines)
  - `src/agent/graph.py` — Legacy Stage 3 single-agent graph (LangGraph Studio entrypoint)
  - `src/agent/agent.py` — Legacy single-agent wrapper with checkpointer
  - `src/agent/llm.py` — LLM factory with 5 providers and 3-tier model pyramid
  - `src/agent/concurrency.py` — Per-tier semaphore gating (`_SemaphoreLLM`)
  - `src/agent/renderer.py` — Handbook rendering (HTML/Markdown/JSON via Jinja2 + Pydantic)
  - `src/agent/state.py` — `TravelAgentState` TypedDict with custom reducers
- `src/tools/` — 13 LangChain `@tool` functions (flights, hotels, weather, RAG, Google Maps, currency, safety, web search, IATA)
- `src/rag/` — Pinecone-backed RAG pipeline: chunker, embeddings, indexer, query decomposer, Cohere reranker
- `src/models/` — Pydantic data models (`TripHandbook`, `FlightOption`, `HotelOption`, `DayPlan`, etc.) and 8 StrEnums
- `src/api/` — FastAPI server with async SSE streaming, rate limiting, CORS, HITL interrupts
- `src/mcp_server.py` — MCP server (stdio transport) exposing 16 tools for external AI agents
- `src/evaluation/` — Four-layer evaluation: code-based, LLM-as-judge, RAG metrics + 30+ golden dataset cases
- `src/data/` — Static data files (`iata_codes.csv` — ~7,700 airports)

### Frontend (TypeScript)
- `frontend/` — Next.js 16 + React 19 + TypeScript + Tailwind CSS 4 + shadcn/ui
  - `frontend/src/app/` — App Router with `(chat)/` route group
  - `frontend/src/components/` — Chat UI (7), results cards (6), HITL components, 20 shadcn/ui primitives
  - `frontend/src/stores/` — Zustand store (`chat-store.ts`)
  - `frontend/src/lib/` — API client, types, utilities (React Query for data fetching)

### Infrastructure & Config
- `config/config.yaml` — Logging, RAG, routing, timeouts configuration
- `k8s/` — Kubernetes manifests (deployment, service, configmap, postgres, redis, kind-config)
- `docker-compose.yml`, `Dockerfile` — Docker containerization
- `knowledge_base/destination_guides/` — Markdown travel guides (Wikivoyage-style)
- `tests/` — 28 test files, pytest with `respx` mocking and `asyncio_mode = "auto"`
- `scripts/` — Utility scripts (eval, download, debug, live API testing)
- `docs/` — Architecture, tools, reference, getting-started, operations documentation
- `.github/agents/` — 4 custom Copilot agents (knowledge-base-writer, prompt-engineer, reviewer, test-writer)
- `.github/prompts/` — Reusable prompt templates (system design, PR generation)
- `.github/workflows/ci.yml` — CI/CD pipeline

## Code Conventions

### Python
- Python 3.12+ — use `list[str]`, `dict[str, Any]`, `X | None` (not `Optional[X]`)
- Use `from __future__ import annotations` only if needed for forward refs
- Imports: stdlib → third-party → local, separated by blank lines
- All tools are decorated with `@tool` from `langchain_core.tools`
- All agents extend `SpecializedAgent` from `src/agent/agents/base.py`
- Prompts live in `src/agent/prompts/agent_prompt.py` and are exported via `__init__.py`
- Use `custom_logging.AppLogger` for logging, not `print()` or bare `logging`
- Response content extraction must handle both Chat Completions (str) and Responses API (list of blocks) formats

### Frontend (TypeScript)
- Next.js 16 App Router with `(chat)/` route group
- Zustand for global state, React Query (`@tanstack/react-query`) for server data
- `react-hook-form` + `zod` for form handling and validation
- Tailwind CSS 4 + shadcn/ui component library (20 primitives in `components/ui/`)
- Path alias: `@/*` → `./src/*`
- API calls proxied via Next.js rewrites: `/api/v1/*` → FastAPI backend

### Testing
- Use **pytest** with **async** tests (`async def test_...`)
- Mock HTTP with **`respx`**, not `unittest.mock` or `responses`
- Mock payloads as module-level `_MOCK_*` constants
- Use `monkeypatch.setenv()` for API keys in tests
- One test file per module: `test_{module}.py` (28 test files currently)
- Integration tests use `@pytest.mark.integration` and `@pytest.mark.skipif` on missing API keys
- conftest.py disables LangSmith tracing and defines skip markers: `skip_no_openweather`, `skip_no_exchangerate`, `skip_no_duffel`, `skip_no_google_maps`, `skip_no_hotelbeds`, `skip_no_azure_openai`
- Coverage target: 80% (`fail_under: 80`); excludes: `src/api`, `src/mcp_server.py`, legacy agents, `llm.py`, `renderer.py`, `golden_dataset.py`
- Run: `make test` (all), `make test-unit` (unit only), `make coverage` (with report)

### Git
- Conventional commits: `<type>(<scope>): <summary>`
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`, `perf`
- Scope: module name (`agent`, `tools`, `rag`, `graph`, `prompts`, `api`, `frontend`, `k8s`)
- Group commits by category when multiple changes exist

## Architecture

### Graph Flow (Stage 4 — `stage4_graph.py`)
```
START → TRIAGE → shallow_reply (simple queries) → END
              → SUPERVISOR (routing + user profiling)
                  → [Send() fan-out: 6 parallel agents]
                  │  flights, hotels, destination,
                  │  restaurants, activities, transportation
                  → FAN-IN → SAFETY_REVIEW (HITL gate)
                  → BUDGET (sequential) → BUDGET_REVIEW (HITL gate)
                  → ITINERARY (sequential) → HUMAN_REVIEW (HITL gate)
                  → RENDER_HANDBOOK → END
              → SYNTHESIZE (follow-ups from existing data) → END
```

### Three-Tier LLM Pyramid
| Tier | Model | TPM | Agents | Semaphore | Reasoning Effort |
|------|-------|-----|--------|-----------|------------------|
| `reasoning` | gpt-5.4 | 300K | Destination, Itinerary | 4 | medium |
| `fast` | gpt-5.4-mini | 500K | Flights, Hotels, Restaurants, Activities, Transportation, Budget | 15 | low |
| `utility` | gpt-5.4-nano | 200K | Supervisor, Triage, Rendering, Shallow replies | 15 | low |

> **Source of truth (verify, do not trust this table blindly):** semaphore caps = `_SEMAPHORE_LIMITS` in `src/agent/concurrency.py`; reasoning effort = `_TIER_REASONING_EFFORT` in `src/agent/llm.py`; TPM reflects your Azure deployment quota. This table is a summary and drifts easily — the code wins.

All gpt-5.4 family models are **reasoning models**. Key constraints:
- Tool calling is NOT supported in Chat Completions with `reasoning: none` (the default)
- The Responses API (`use_responses_api=True`) is enabled for all tiers in `llm.py`
- Content from Responses API is a `list[dict]` of blocks, not a `str` — always use `_extract_text_content()` to read `message.content`

### Supported LLM Providers
`azure_openai` (default), `openai`, `anthropic`, `google`, `ollama` — set via `LLM_PROVIDER` env var

### State Management
- `TravelAgentState` extends `MessagesState` (TypedDict)
- Key fields: `session_id`, `current_agent`, `itinerary_components` (parallel merge), `destinations`, `travel_style`, `group_type`, `accessibility_needs`, `dietary_restrictions`, `human_feedback`, `hitl_action`, `handbook_paths`
- Custom reducers: `_merge_components` (shallow-merge for parallel `Send()` workers), `_last_value` (last-write-wins)
- Access state fields with `.get("field", default)` — never attribute access

### HITL Gates (Human-in-the-Loop)
- **safety_review**: Interrupts on "do not travel" / "red" advisory
- **budget_review**: Interrupts if budget overspends >$500
- **human_review**: User reviews itinerary before rendering
- Uses LangGraph `interrupt()` to pause + `Command(resume=...)` to continue

### Tools (13 `@tool` functions)
| Tool | API | Module |
|------|-----|--------|
| `search_flights` | Duffel | `tools/flights_duffel.py` |
| `search_nearby_airports` | Duffel | `tools/flights_duffel.py` |
| `search_hotels_hotelbeds`, `check_hotel_rate_hotelbeds` | Hotelbeds Booking API | `tools/hotels_hotelbeds.py` |
| `search_activities` | Google Places (New) | `tools/activities.py` |
| `search_places_nearby`, `search_places_text` | Google Places | `tools/google_maps.py` |
| `compute_route`, `optimize_day_route` | Google Routes | `tools/google_maps.py` |
| `get_timezone` | Google Time Zone | `tools/google_maps.py` |
| `search_destination_guides` | Pinecone RAG | `tools/destination_rag.py` |
| `research_destination` | RAG + Tavily + Cohere reranking | `tools/destination_research.py` |
| `search_web`, `search_hidden_gems` | Tavily Search | `tools/web_search.py` |
| `get_weather` | OpenWeatherMap | `tools/weather.py` |
| `get_safety_info` | REST Countries | `tools/safety.py` |
| `calculate_budget` | Pure Python (region baselines × style multipliers) | `tools/budget.py` |
| `convert_currency` | ExchangeRate API | `tools/currency.py` |
| `lookup_iata_code` | Local CSV (~7,700 airports) | `tools/iata.py` |

### RAG Pipeline
- **Chunking**: Section-level (24 travel sections) + `RecursiveCharacterTextSplitter` fallback (2000 chars, 200 overlap)
- **Embeddings**: Azure OpenAI (3072 dimensions), batch embedding with retry
- **Vector store**: Pinecone serverless, cosine similarity
- **Multi-tenant**: Client namespace first (e.g., `acme_travel/destination_guides`), falls back to `wikivoyage/destination_guides`
- **Query decomposition**: LLM decomposes broad queries into 1–4 focused sub-queries
- **Reranking**: Cohere `rerank-v3.5` cross-encoder (optional, degrades gracefully)
- **Staleness detection**: SHA-256 manifest hashing; re-index only when guides change

### API Layer (FastAPI)
- `POST /api/v1/chat` — Synchronous response
- `POST /api/v1/chat/stream` — SSE streaming (events: `session`, `node`, `component`, `interrupt`)
- Rate limiter: 20 req/session per 60s
- Middleware: error handler, request-ID injection, CORS
- 120s request timeout; LangSmith `@traceable` integration

### MCP Server
- Stdio transport, exposes 16 tools + 2 resources (destination guides, tool reference)
- Server name: `wanderlisted-travel`

### Handbook Rendering
- `HandbookRenderer` produces HTML (Jinja2), Markdown, JSON
- Per-section LLM extraction with retry and batched parallel processing
- Season palettes (40+ destination × season combinations) for themed HTML output
- Google Maps embeds for hotels and route maps

## Build & Run
- `make install` — Create venv, install dependencies
- `make dev` — Start FastAPI (`uvicorn src.api.main:app --reload` on :8000)
- `make frontend` — Start Next.js dev on :3000
- `make test` / `make test-unit` / `make coverage` — Testing
- `make lint` / `make fmt` — Ruff linting and formatting
- `make reindex` — Re-index knowledge base into Pinecone
- `make docker-up` / `make docker-down` — Docker Compose
- `make k8s-up` / `make k8s-status` — Kind local Kubernetes cluster

## MCP Servers
- Always use the OpenAI developer documentation MCP server (`openaiDeveloperDocs`) when working with the OpenAI API, Responses API, Agents SDK, or any OpenAI product — without being explicitly asked.

## What NOT to Do
- Don't add `__pycache__/`, `.env`, or API keys to commits
- Don't use `print()` for logging in `src/` — always use `custom_logging.AppLogger`
- Don't create new agents without adding them to `src/agent/agents/__init__.py`, the supervisor prompt, and `VALID_AGENT_NAMES` in `supervisor_agent.py`
- Don't add tools that make unscoped network calls without timeout and error handling
- Don't use `unittest.mock` or `responses` for HTTP mocking — use `respx`
- Don't access `TravelAgentState` fields as attributes — always use `.get("field", default)`
- Don't modify `graph.py` or `agent.py` — they are legacy entrypoints; the primary graph is `stage4_graph.py`
- Don't hardcode LLM model names — use `get_llm(tier=...)` from `src/agent/llm.py`
