# Wanderlisted — Copilot Instructions

## Project Overview
Wanderlisted is a **multi-agent AI travel itinerary planner** built with Python 3.12+, LangChain, LangGraph, and LangSmith. It uses a supervisor-routed architecture where specialized agents (Flights, Hotels, Destination, Restaurants, Activities, Transportation, Budget, Itinerary) run in parallel to produce personalized travel itineraries.

## Project Structure
- `src/agent/` — LangGraph graphs, agent definitions, state, prompts
- `src/agent/agents/` — Specialized agents (one file per agent, extends `SpecializedAgent`)
- `src/agent/prompts/` — All system prompts in `agent_prompt.py`
- `src/tools/` — LangChain tools (flights, hotels, weather, RAG, Google Maps, etc.)
- `src/rag/` — Pinecone-backed RAG: chunker, embeddings, indexer
- `src/models/` — Pydantic data models
- `knowledge_base/destination_guides/` — Markdown travel guides (Wikivoyage-style)
- `tests/` — Pytest suite with `respx` mocking and `asyncio_mode = "auto"`
- `config/config.yaml` — Runtime configuration
- `scripts/` — Utility scripts (eval, download, test)

## Code Conventions

### Python
- Python 3.12+ — use `list[str]`, `dict[str, Any]`, `X | None` (not `Optional[X]`)
- Use `from __future__ import annotations` only if needed for forward refs
- Imports: stdlib → third-party → local, separated by blank lines
- All tools are decorated with `@tool` from `langchain_core.tools`
- All agents extend `SpecializedAgent` from `src/agent/agents/base.py`
- Prompts live in `src/agent/prompts/agent_prompt.py` and are exported via `__init__.py`
- Use `custom_logging.AppLogger` for logging, not `print()` or bare `logging`

### Testing
- Use **pytest** with **async** tests (`async def test_...`)
- Mock HTTP with **`respx`**, not `unittest.mock` or `responses`
- Mock payloads as module-level `_MOCK_*` constants
- Use `monkeypatch.setenv()` for API keys in tests
- One test file per module: `test_{module}.py`
- Run: `pytest` (unit) or `pytest -m integration` (live API tests)

### Git
- Conventional commits: `<type>(<scope>): <summary>`
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`, `perf`
- Scope: module name (`agent`, `tools`, `rag`, `graph`, `prompts`)
- Group commits by category when multiple changes exist

### Architecture Patterns
- Supervisor → parallel fan-out → sequential finishers (Budget → Itinerary)
- State via `TravelAgentState` (TypedDict extending `MessagesState`)
- Access state fields with `.get("field", default)` — never attribute access
- User profile (destinations, travel_style, group_type, dietary_restrictions, accessibility_needs) is extracted by supervisor and injected into every subagent's context
- RAG uses Pinecone with metadata filtering by `destination` slug

## What NOT to Do
- Don't add `__pycache__/`, `.env`, or API keys to commits
- Don't use `print()` for logging in `src/`
- Don't create new agents without adding them to `src/agent/agents/__init__.py` and the supervisor prompt
- Don't add tools that make unscoped network calls without timeout and error handling
