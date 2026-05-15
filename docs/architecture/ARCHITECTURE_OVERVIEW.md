# Architecture Overview

> Multi-agent supervisor architecture with parallel fan-out, sequential finishers, and human-in-the-loop gates.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Execution Flow](#execution-flow)
- [Agent Roster](#agent-roster)
- [State Management](#state-management)
- [LLM Model Tiers](#llm-model-tiers)
- [RAG Pipeline](#rag-pipeline)
- [Human-in-the-Loop Gates](#human-in-the-loop-gates)
- [Handbook Rendering](#handbook-rendering)
- [Key Source Files](#key-source-files)

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI / LangServe endpoint                                    │
│  POST /invoke  •  POST /stream                                   │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │     Triage     │  Classifies: shallow vs deep query
              └───────┬────────┘
           ┌──────────┴──────────┐
           ▼                     ▼
   ┌───────────────┐    ┌───────────────┐
   │ Shallow Reply │    │  Supervisor   │  Extracts user profile,
   │   → END       │    │               │  decides routing
   └───────────────┘    └───────┬───────┘
                                │
        ┌──────────Send()───────┼──────────Send()──────┐
        ▼          ▼            ▼           ▼          ▼           ▼
   ┌─────────┐ ┌────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
   │ Flights │ │ Hotels │ │Destination│ │Restaurants│ │Activities│ │Transportation│
   └────┬────┘ └───┬────┘ └────┬──────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘
        │          │           │              │            │               │
        └──────────┴───────────┴──────────────┴────────────┴───────────────┘
                                      │
                                      ▼  (fan-in — all parallel agents complete)
                            ┌──────────────────┐
                            │  Safety Review   │  HITL gate: interrupts on red advisory
                            └────────┬─────────┘
                                     ▼
                            ┌──────────────────┐
                            │     Budget       │  Sequential — needs flight/hotel prices
                            └────────┬─────────┘
                                     ▼
                            ┌──────────────────┐
                            │  Budget Review   │  HITL gate: interrupts if > $500 overspend
                            └────────┬─────────┘
                                     ▼
                            ┌──────────────────┐
                            │    Itinerary     │  Sequential — needs all data
                            └────────┬─────────┘
                                     ▼
                            ┌──────────────────┐
                            │  Human Review    │  HITL gate: user reviews full itinerary
                            └────────┬─────────┘
                                     ▼
                            ┌──────────────────┐
                            │ Render Handbook  │  TripHandbook → HTML/MD/JSON via Jinja2
                            └────────┬─────────┘
                                     ▼
                                    END
```

Follow-up questions after the initial plan bypass the full pipeline:

```
User follow-up → Triage → Supervisor → Synthesize → END
                                         (uses existing agent data, no re-run)
```

---

## Execution Flow

1. **Triage** — Fast LLM (nano) classifies the user message:
   - *Shallow*: greetings, clarifications, simple follow-ups → direct reply
   - *Deep*: full travel planning request → supervisor

2. **Supervisor** — Fast LLM (nano) extracts a `RoutingDecision`:
   - `destinations: list[str]` — where the user wants to go
   - `travel_style: str` — budget / mid-range / luxury
   - `group_type: str` — solo / couple / family / friends
   - `dietary_restrictions: str`
   - `accessibility_needs: str`
   - Routes to the 6 parallel agents via `Send()` messages

3. **Parallel Fan-Out** — 6 agents execute concurrently:
   - Each agent receives the full state + user profile
   - Each writes results to `itinerary_components[agent_key]`
   - LangGraph's `Send()` mechanism handles fan-out and fan-in

4. **Safety Review** — HITL interrupt if advisory is red/do-not-travel
   - User must acknowledge before proceeding

5. **Budget Agent** — Runs sequentially after parallel phase
   - Receives flight/hotel costs from prior agents
   - Computes full budget breakdown

6. **Budget Review** — HITL interrupt if budget exceeds target by >$500

7. **Itinerary Agent** — Assembles the day-by-day plan
   - Optimizes daily routes using Google Routes
   - Assigns time blocks (morning/afternoon/evening)
   - Integrates all prior agent data

8. **Human Review** — User reviews assembled itinerary
   - Can approve, reject, or request modifications

9. **Render Handbook** — Extracts structured `TripHandbook` from agent data
   - Per-section LLM extraction into Pydantic models
   - Renders via Jinja2 to HTML, Markdown, and JSON

---

## Agent Roster

| Agent | Phase | Specialization | Key Tools |
|-------|-------|---------------|-----------|
| **SupervisorAgent** | Routing | User profile extraction, agent dispatch | — |
| **FlightsAgent** | Parallel | Flight search, airport codes, connections | `lookup_iata_code`, `search_flights` |
| **HotelsAgent** | Parallel | Hotel search (Hotelbeds), rate verification | `search_hotels_hotelbeds`, `check_hotel_rate_hotelbeds` |
| **DestinationAgent** | Parallel | City research, weather, safety, local knowledge (RAG) | `research_destination`, `search_destination_guides`, `get_weather`, `get_safety_info` |
| **RestaurantsAgent** | Parallel | Restaurant discovery by cuisine, neighborhood, budget | `search_places_nearby`, `search_places_text` |
| **ActivitiesAgent** | Parallel | Attractions, tours, experiences, things to do | `search_places_nearby`, `search_places_text` |
| **TransportationAgent** | Parallel | Airport transfers, city transit, inter-city routes | `get_directions`, `get_distance_matrix`, `compute_route` |
| **BudgetAgent** | Sequential | Cost estimation, currency conversion, budget breakdown | `calculate_budget`, `convert_currency` |
| **ItineraryAgent** | Sequential | Day-by-day planning, route optimization | `optimize_day_route`, `get_distance_matrix` |

---

## State Management

All agents share `TravelAgentState`, a `TypedDict` extending LangGraph's `MessagesState`.

### Key State Fields

| Field | Type | Purpose |
|-------|------|---------|
| `messages` | `list[BaseMessage]` | Chat history (inherited from MessagesState) |
| `session_id` | `str` | Unique conversation identifier |
| `current_agent` | `str` | Currently executing agent name |
| `itinerary_components` | `dict[str, Any]` | Output from all agents (merge reducer for Send) |
| `destinations` | `list[str]` | Extracted destinations |
| `travel_style` | `str` | budget / mid-range / luxury |
| `group_type` | `str` | solo / couple / family / friends / group |
| `accessibility_needs` | `str` | Wheelchair, mobility, etc. |
| `dietary_restrictions` | `str` | Vegetarian, halal, allergies, etc. |
| `handbook_paths` | `dict[str, str]` | Output file paths (html, md, json) |
| `human_feedback` | `str` | User's feedback from HITL gates |
| `hitl_action` | `str` | approve / reject / modify |
| `safety_acknowledged` | `bool` | User acknowledged safety advisory |
| `budget_adjustment_accepted` | `bool` | User accepted budget revision |

### State Access Pattern

Always use `.get()` with defaults — never attribute access:

```python
# ✅ Correct
destinations = state.get("destinations", [])
style = state.get("travel_style", "mid-range")

# ❌ Wrong — raises KeyError if missing
destinations = state["destinations"]
style = state.travel_style
```

---

## LLM Model Tiers

Wanderlisted uses a 3-tier model strategy to balance quality and cost:

| Tier | Model | Used For |
|------|-------|----------|
| **Reasoning** | gpt-4.1 (or configured) | Destination research, itinerary assembly — deep reasoning tasks |
| **Fast** | gpt-4.1-mini | Flights, Hotels, Restaurants, Activities, Transportation, Budget — structured tool calling |
| **Utility** | gpt-4.1-nano | Triage, supervisor routing, shallow replies, handbook rendering, synthesis — low-complexity |

Models are configured in `config/config.yaml` and instantiated via `ChatOpenAI` or `AzureChatOpenAI`.

---

## RAG Pipeline

The Destination research system uses a Pinecone-backed RAG pipeline.

```
Knowledge Base (Markdown guides)
        │
        ▼
  Chunker (recursive by headings + size, 2000 chars, 200 overlap)
        │
        ▼
  OpenAI Embeddings (text-embedding-3-small)
        │
        ▼
  Pinecone Vector DB (metadata: destination slug, section, tenant)
        │
        ▼
  Query Decomposition (up to 4 sub-queries)
        │
        ▼
  Retrieval (top_k=5 per sub-query, metadata filter by destination)
        │
        ▼
  Cohere Reranker v3.5 (optional, top_n=5)
        │
        ▼
  Context → LLM → Research answer
```

See `docs/architecture/CHUNKING_STRATEGY_RATIONALE.md` for the chunking design rationale.

---

## Human-in-the-Loop Gates

Three interrupt points ensure user oversight over critical decisions:

| Gate | Trigger | User Action |
|------|---------|-------------|
| **Safety Review** | Advisory level is red / do-not-travel | Acknowledge risk → continue, or abort |
| **Budget Review** | Estimated total exceeds budget by > $500 | Accept → continue, adjust → re-plan, reject → abort |
| **Human Review** | Full itinerary assembled | Approve → render, modify → re-plan sections, reject → start over |

HITL is implemented via LangGraph's `interrupt()` function. The graph pauses, sends the current state to the client, and waits for a `Command(resume=...)` to continue.

---

## Handbook Rendering

The final output is a `TripHandbook` — a rich Pydantic model containing all trip data, rendered into multiple formats:

| Format | File | Use Case |
|--------|------|----------|
| HTML | `outputs/handbook.html` | Share, print, or view in browser |
| Markdown | `outputs/handbook.md` | Version control friendly |
| JSON | `outputs/handbook.json` | Programmatic consumption |

The renderer uses Jinja2 templates with themed styling. Each section (flights, hotels, days, budget, safety, etc.) is extracted independently via LLM structured output into the corresponding Pydantic model.

---

## Key Source Files

| File | Purpose |
|------|---------|
| `src/agent/stage4_graph.py` | Main LangGraph graph definition |
| `src/agent/agents/base.py` | `SpecializedAgent` abstract base class |
| `src/agent/agents/*.py` | Individual agent implementations |
| `src/agent/prompts/agent_prompt.py` | All system prompts |
| `src/agent/state.py` | `TravelAgentState` TypedDict |
| `src/agent/nodes.py` | Graph node functions (triage, supervisor, agent runner, etc.) |
| `src/tools/*.py` | Tool implementations |
| `src/models/itinerary.py` | `TripHandbook` and all data models |
| `src/models/enums.py` | StrEnum types |
| `src/api/app.py` | FastAPI / LangServe API |
| `config/config.yaml` | Runtime configuration |
