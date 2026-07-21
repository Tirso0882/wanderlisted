# Wanderlisted — Multi-Agent Travel Itinerary System Design

> **Author:** Tirso Gomez
> **Date:** March 2026
> **Stack:** Python · LangChain · LangGraph · LangSmith
> **Purpose:** A production-grade reference for building a multi-agent system that generates rich, personalised travel itineraries — and a learning roadmap for mastering multi-agent architecture patterns.

---

## 1. High-Level Narrative Overview

### What We're Building

Wanderlisted is a multi-agent orchestration system that accepts a natural-language travel request (e.g., *"Plan a 10-day trip to Japan for two people in April, budget $4,000 USD"*) and returns a fully structured, personalised travel handbook — including flights, hotels, day-by-day activities, weather context, cost summaries, safety advisories, and cultural tips.

### Why Multi-Agent?

A monolithic LLM cannot reliably generate accurate flight prices, live weather, real exchange rates, and detailed activity itineraries simultaneously. The hallucination risk is high, tool-calling becomes unwieldy, and the context window fills fast. Instead, we divide the problem into **focused specialist agents** — each with a narrow responsibility, managed inputs and outputs, and clear interaction contracts — coordinated by a supervisor graph that assembles them into a coherent whole.

### The Core Insight

> Think of Wanderlisted as a travel agency — not a single travel consultant. The supervisor is the account manager who takes the client brief and delegates to specialists: a flight desk, a hotels desk, a local experiences team, and a finance analyst. Each specialist does one job well and hands off structured results. The account manager synthesises everything into the final itinerary handbook.

This pattern — a **supervisor-routed multi-agent graph** — is directly transferable to hundreds of other domains. Mastering it here means you can build the same architecture for medical triage, legal research, e-commerce product discovery, and more.

### Technology Stack Fit

| Layer | Technology | Role |
|---|---|---|
| **Agent intelligence** | LangChain (tools, structured output, LCEL chains) | Each specialist agent's core reasoning |
| **Orchestration** | LangGraph (StateGraph, supervisor, sub-graphs, Send API) | Graph structure, routing, parallelism, memory |
| **Observability** | LangSmith (tracing, evaluation, prompt versioning) | Debug, evaluate quality, monitor production |
| **State persistence** | LangGraph Checkpointer (SQLite → Postgres) | Memory across turns, HITL, time travel |

---

## 2. Agent-by-Agent Evaluation

Each tool or capability below is evaluated as: **standalone agent** or **tool within an agent**, based on complexity of reasoning required, state ownership, interactivity, and re-usability.

---

### 2.1 FlightSearchAgent ✅ Standalone Agent

**Purpose:** Searches for available flights between an origin and destination for given dates and passenger count.

**Value it adds:** Flight data is dynamic, structured, and meaningfully complex — round-trips, layovers, airline preferences, cabin class, fare rules, baggage. A dedicated agent can reason over multiple search results and rank or filter them against user preferences.

**Required inputs:**
- `origin_iata` (string) — departure airport code
- `destination_iata` (string) — arrival airport code
- `departure_date` (ISO 8601)
- `return_date` (ISO 8601, optional)
- `passengers` (int)
- `cabin_class` (string: economy / business)
- `budget_ceiling_usd` (float, optional)

**Required outputs:**
- `flight_options` (list of structured `FlightOption` Pydantic objects: airline, flight number, price, duration, stops, booking link)
- `recommended_option` (single best match with reasoning)

**Tools / APIs:** Duffel Offer Requests API · Tavily web search (fallback)

**Interacts with:**
- `IATALookupTool` — resolves city/airport names to IATA codes before calling the API
- `BudgetAgent` — passes prices for cost roll-up
- `FlightBookingAgent` — hands off selected `FlightOption` for booking

**Should it be a separate agent?** **Yes.** Flight search requires iterative tool calls (search → filter → rank), structured output schemas, and potential human-in-the-loop review of results. Its state is self-contained.

---

### 2.2 FlightBookingAgent ✅ Standalone Agent (Phase 3+, HITL Required)

**Purpose:** Books the selected flight using traveller details and payment information.

**Value it adds:** Booking is a **high-stakes, irreversible action**. It must be a separate agent gated behind a mandatory human-in-the-loop interrupt (`interrupt_before=["booking_action"]`) so the user confirms before any real-world write happens.

**Required inputs:**
- `selected_flight` (`FlightOption` from FlightSearchAgent)
- `traveller_details` (name, passport, DOB)
- `payment_token` (securely injected at runtime — never in state)

**Required outputs:**
- `booking_confirmation` (confirmation number, e-ticket link, PNR)
- `booking_status` (confirmed / failed / pending)

**Tools / APIs:** Duffel Order API · Airline booking APIs

**Interacts with:**
- `FlightSearchAgent` — consumes its output
- `Supervisor` — must interrupt before executing

**Security note:** Payment credentials must **never** be stored in LangGraph state (checkpointer persistence). Inject via `RunnableConfig` at call-time using `configurable` fields and rotate tokens per session.

**Should it be a separate agent?** **Yes, and deliberately deferred.** Its irreversible side-effects and security requirements justify isolation. Build phases 1–2 without it; introduce it with a HITL gate in Phase 3.

---

### 2.3 HotelSearchAgent ✅ Standalone Agent

**Purpose:** Searches for available hotels in the destination city for the given dates, filtering by budget and preferences.

**Value it adds:** Hotel search involves nuanced preference matching (location vs. price, amenity filtering, neighbourhood character) and produces structured results that feed the cost summary and day-by-day itinerary. Separating it allows parallel execution with flight search.

**Required inputs:**
- `destination_city` (string)
- `check_in_date` / `check_out_date` (ISO 8601)
- `guests` (int)
- `budget_per_night_usd` (float)
- `preferences` (list: "central", "historic", "quiet", "boutique", etc.)

**Required outputs:**
- `hotel_options` (list of structured `HotelOption` Pydantic objects)
- `recommended_option` (with reasoning)

**Tools / APIs:** Hotelbeds Booking API · Tavily web search (fallback)

**Interacts with:**
- `BudgetAgent` — passes hotel total cost
- `ActivitiesAgent` — provides neighbourhood context to help plan nearby activities

**Should it be a separate agent?** **Yes.** Parallel with FlightSearchAgent via LangGraph fan-out (`Send` API or parallel edges). Both can run simultaneously after the `user_context_node`.

---

### 2.4 WeatherAgent ✅ Standalone Agent (lightweight)

**Purpose:** Retrieves weather forecasts and historical climate data for the destination across the travel dates.

**Value it adds:** Weather data shapes the entire itinerary — outdoor activities, packing advice, clothing tips, and risk advisories. Without it, the system generates generic recommendations.

**Required inputs:**
- `destination_city` (string)
- `travel_dates` (list of ISO 8601 dates)

**Required outputs:**
- `daily_weather` (list of `DayWeather`: date, temp range, conditions, precipitation probability)
- `climate_summary` (two-sentence narrative)
- `packing_recommendations` (list of items)

**Tools / APIs:** OpenWeatherMap API · Weather.gov · Tavily (historical climate context)

**Interacts with:**
- `ActivitiesAgent` — weather context used to schedule indoor/outdoor activities appropriately
- `ItineraryAssemblerAgent` — injects weather notes per day

**Should it be a separate agent?** **Yes, but keep it slim.** A single-node ReAct agent with tool access is sufficient. It does not need complex reasoning — just structured tool calls and formatted output.

---

### 2.5 CurrencyAgent ✅ Standalone Agent (lightweight)

**Purpose:** Retrieves current exchange rates between the user's home currency and destination currencies, and provides spending-power context.

**Value it adds:** Without real exchange rates, budget calculations are meaningless. It also enriches the itinerary with practical spending tips (e.g., tipping culture, cash vs. card norm).

**Required inputs:**
- `home_currency` (ISO 4217, e.g., "USD")
- `destination_currency` (ISO 4217, e.g., "JPY")
- `budget_usd` (float)

**Required outputs:**
- `exchange_rate` (float)
- `budget_local_currency` (float)
- `spending_tips` (list of strings)
- `last_updated` (ISO 8601 timestamp)

**Tools / APIs:** Open Exchange Rates API · Frankfurter API (free) · Tavily (spending culture context)

**Interacts with:**
- `BudgetAgent` — provides the rate used for all conversions

**Should it be a separate agent?** **Yes**, but this is a candidate for a **single-node agent** rather than a full sub-graph. Since it makes one deterministic tool call and returns structured data, it can be implemented as a simple LangChain chain (`prompt | model.with_structured_output(CurrencyResult)`) invoked as a tool node within the supervisor.

---

### 2.6 ActivitiesAgent ✅ Standalone Agent

**Purpose:** Generates a curated list of day-by-day activities, restaurants, cultural experiences, and hidden gems based on the destination, travel style, weather, and interests.

**Value it adds:** This is the **richest creative agent** in the system. It synthesises destination knowledge, user preferences, and contextual data (weather, neighbourhood, cultural calendar) into a compelling human experience narrative. This is where the most LLM reasoning power should be invested.

**Required inputs:**
- `destination` (city or region)
- `travel_dates` (list)
- `travel_style` (list: "cultural", "adventure", "relaxation", "foodie", etc.)
- `interests` (free text)
- `weather_context` (`daily_weather` from WeatherAgent)
- `hotel_neighbourhood` (string from HotelSearchAgent)
- `budget_per_day_usd` (float from BudgetAgent)

**Required outputs:**
- `day_plans` (list of `DayPlan`: date, morning/afternoon/evening activities, restaurants, cultural notes, estimated costs)
- `must_see` (shortlist of top highlights)
- `hidden_gems` (shortlist of under-the-radar recommendations)

**Tools / APIs:** Tavily web search · Google Places API · Foursquare API · Wikipedia (cultural context via LangChain WikipediaLoader)

**Interacts with:**
- `WeatherAgent` — consumes weather to shape outdoor/indoor scheduling
- `SafetyAgent` — safety flags can suppress certain activities or add advisories
- `ItineraryAssemblerAgent` — provides the core content of each day

**Should it be a separate agent?** **Yes, and this is the most complex agent.** It benefits from a ReAct loop: search → evaluate result → decide to search further or generate plan. Consider a **sub-graph** with its own `ActivitiesState` to keep the message history clean.

---

### 2.7 SafetyAgent ✅ Standalone Agent (cross-cutting concern)

**Purpose:** Retrieves up-to-date travel advisories, health requirements (vaccinations, visa), local safety tips, and emergency contacts for the destination.

**Value it adds:** Safety information is non-negotiable and should never be omitted. It adds credibility and genuine user value. Its outputs are injected into every relevant section of the final handbook.

**Required inputs:**
- `destination_country` (ISO 3166-1 alpha-2)
- `home_country` (for visa context)
- `travel_dates` (for seasonal health/event context)

**Required outputs:**
- `advisory_level` (string: "safe" / "exercise caution" / "reconsider" / "do not travel")
- `visa_requirements` (string)
- `health_requirements` (list: vaccinations, medications)
- `emergency_contacts` (police, ambulance, embassy)
- `local_safety_tips` (list)
- `natural_disaster_risk` (string, seasonal)

**Tools / APIs:** US State Department Travel Advisories API · UK FCDO API · CDC Traveler's Health · Tavily web search

**Interacts with:**
- `ActivitiesAgent` — flags unsafe activities or areas
- `ItineraryAssemblerAgent` — safety section injected into final output
- `Supervisor` — if advisory level is "do not travel", supervisor should interrupt and alert the user

**Should it be a separate agent?** **Yes**, but its outputs are **injected into every other agent's context** as a cross-cutting concern. Run it early and in parallel with FlightSearchAgent and HotelSearchAgent. Never let activities be planned without first running SafetyAgent.

---

### 2.8 BudgetAgent ✅ Standalone Agent

**Purpose:** Aggregates cost estimates from all other agents, applies exchange rates, and produces a comprehensive budget breakdown with projections.

**Value it adds:** Closing the budget loop is what transforms a collection of agent outputs into a coherent, trustworthy plan. The user asked for a `$4,000` trip — BudgetAgent tells them definitively whether the assembled plan is within budget and where to adjust.

**Required inputs:**
- `flight_cost_usd` (from FlightSearchAgent)
- `hotel_cost_usd` (from HotelSearchAgent)
- `activity_costs_usd` (from ActivitiesAgent)
- `daily_meal_budget_usd` (from user preferences)
- `exchange_rate_data` (from CurrencyAgent)
- `total_budget_usd` (from original user request)

**Required outputs:**
- `budget_breakdown` (dict: flights, hotels, activities, meals, transport, misc)
- `total_estimated_usd` (float)
- `total_estimated_local` (float)
- `under_over_budget` (float — positive = under, negative = over)
- `saving_recommendations` (list, if over budget)

**Tools / APIs:** No external APIs needed. Pure calculation + LLM for narrative recommendations. Consider `with_structured_output(BudgetSummary)`.

**Interacts with:**
- All agents (final aggregation point)
- `ItineraryAssemblerAgent` — budget summary section injects into the final output

**Should it be a separate agent?** **Yes**, but it is a **fan-in node** — it runs after all cost-bearing agents complete. It does not need to be a ReAct loop; a single LLM chain call with structured output is sufficient.

---

### 2.9 IATALookupTool — ⚠️ Tool, Not an Agent

**Purpose:** Resolves city or airport names (e.g., "Tokyo" → `NRT` / `HND`) to IATA codes required by flight APIs.

**Value it adds:** Flight APIs require IATA codes; users don't think in IATA codes. Without this, the FlightSearchAgent would fail on natural-language inputs.

**Should it be a separate agent?** **No.** This is a pure lookup — deterministic, stateless, and sub-second. Implement it as a `@tool`-decorated function bound to `FlightSearchAgent`. It involves zero reasoning. Creating an agent for it would add latency and complexity with no benefit. Backed by the Duffel Places API or a static IATA code dictionary with Tavily fallback.

---

## 3. Architecture & Orchestration Plan

### 3.1 Orchestration Model: Hierarchical Supervisor Graph

The recommended architecture is a **supervisor-routed multi-agent graph** implemented in LangGraph, with sub-graphs for the most complex agents.

```
                         ┌─────────────────────────────┐
                         │     TravelSupervisorGraph    │
                         │                             │
     [Human Request] ──► │  user_context_node          │
                         │         │                   │
                         │         ▼                   │
                         │  ┌─────────────┐            │
                         │  │  Supervisor │            │
                         │  │    LLM      │            │
                         │  └──────┬──────┘            │
                         │         │ routes            │
                         │    ┌────┼────┐              │
                         │    ▼    ▼    ▼              │
                         │  [S]  [W]  [H]  (parallel)  │
                         │  [F]               [C]       │
                         │    │    │    │    │          │
                         │    ▼    ▼    ▼    ▼          │
                         │    └────┴────┴────┘          │
                         │         │ fan-in             │
                         │         ▼                    │
                         │    ActivitiesAgent           │
                         │         │                    │
                         │         ▼                    │
                         │     BudgetAgent              │
                         │         │                    │
                         │         ▼                    │
                         │  ItineraryAssembler          │
                         │         │                    │
                         │         ▼                    │
                         │   [Final Handbook]           │
                         └─────────────────────────────┘

Legend: [S]=SafetyAgent [W]=WeatherAgent [H]=HotelSearchAgent
        [F]=FlightSearchAgent [C]=CurrencyAgent
```

### 3.2 State Management

Use a **single `TravelState` TypedDict** at the parent graph level, with `Annotated` reducers on keys written by parallel agents. Sub-agents have private `*State` schemas that only surface their outputs to the parent.

```
TravelState:
  # Input
  user_request: str
  destination: str
  origin: str
  travel_dates: list[str]
  budget_usd: float
  preferences: dict

  # Intermediate (written by parallel agents, reducers applied)
  flight_options: list[FlightOption]           # overwrite
  hotel_options: list[HotelOption]             # overwrite
  daily_weather: list[DayWeather]              # overwrite
  exchange_rate_data: CurrencyResult           # overwrite
  safety_report: SafetyReport                  # overwrite
  agent_errors: Annotated[list, add]           # accumulate failures

  # Sequential outputs
  day_plans: list[DayPlan]
  budget_summary: BudgetSummary
  final_handbook: str

  # Control
  supervisor_next: str                         # routing decision
  human_feedback: str                          # HITL injections
```

### 3.3 Parallel Execution Strategy

After `user_context_node` parses and validates the request, five agents run **in parallel** using LangGraph's fan-out pattern:

```python
# Fan-out: all five start simultaneously
builder.add_edge("user_context_node", "safety_agent")
builder.add_edge("user_context_node", "weather_agent")
builder.add_edge("user_context_node", "flight_search_agent")
builder.add_edge("user_context_node", "hotel_search_agent")
builder.add_edge("user_context_node", "currency_agent")

# Fan-in: activities only starts when all five complete
builder.add_edge("safety_agent",       "activities_agent")
builder.add_edge("weather_agent",      "activities_agent")
builder.add_edge("flight_search_agent","activities_agent")
builder.add_edge("hotel_search_agent", "activities_agent")
builder.add_edge("currency_agent",     "activities_agent")
```

This mirrors the Research Assistant sub-graph pattern from LangGraph Module 4, achieving significant latency reduction. Each agent runs for ~5–15 seconds in parallel rather than ~50–75 seconds sequentially.

### 3.4 Supervisor Routing Logic

The `Supervisor LLM` node uses `model.with_structured_output(NextAction)` to decide routing at key decision points:

- **Route to HITL** if `safety_report.advisory_level == "do not travel"` → interrupt with user warning
- **Route to HITL** if `budget_summary.under_over_budget < -500` → offer to adjust (fewer nights, economy flights)
- **Route to FlightBookingAgent** only if user explicitly requests booking
- **Route to END** once `ItineraryAssembler` produces the final handbook

### 3.5 Failure Handling and Fallbacks

| Failure scenario | Handling strategy |
|---|---|
| Flight API timeout | Retry once; on second failure, populate `flight_options` with Tavily-scraped estimates and flag as "approximate" |
| Hotel API returns 0 results | Relax budget constraint by 20% and retry; if still empty, return top 3 Airbnb-style options via web search |
| Weather API unavailable | Use historical monthly averages from a static data file; annotate output as "historical estimate" |
| Safety API unavailable | Default to US State Department advisory page via Tavily scrape |
| Agent poison/hallucination detected | Each agent output is validated against its Pydantic schema before being written to state. Schema validation failure routes to a `correction_node` that retries with a stricter prompt |
| LLM rate limit | Exponential backoff handled at the `BaseChatModel` level via LangChain retry logic |

LangGraph's `interrupt_before` and `NodeInterrupt` are used as the last-resort safety valve before any write to `TravelState.final_handbook`.

### 3.6 LangSmith Integration

LangSmith provides three layers of value:

**Layer 1 — Tracing (development + production)**
- Set `LANGSMITH_TRACING=true` — LangGraph auto-traces every node, sub-graph, tool call, and LLM invocation
- Each run is tagged with `thread_id` (maps to one user session) and `user_id`
- Every agent's internal ReAct loop is visible as a collapsible sub-trace
- Token usage and latency per node are surfaced automatically

**Layer 2 — Evaluation (CI/CD quality gate)**
- Create a **golden dataset** in LangSmith: 20–30 representative travel requests with reference outputs
- Evaluators:
  - Heuristic: Does the final handbook contain all required sections? (structural completeness score)
  - Heuristic: Is the total estimated cost within 15% of a manually verified estimate? (budget accuracy)
  - LLM-as-Judge: Does the itinerary match the user's stated travel style and interests? (semantic alignment, 1–10)
  - LLM-as-Judge: Is the safety section complete and accurate for the destination? (safety coverage, 1–10)
- Run `evaluate()` on every PR to `main` before deployment

**Layer 3 — Prompt Engineering Lifecycle**
- Store all agent system prompts as versioned LangSmith Hub prompts
- Pull prompts at runtime: `hub.pull("wanderlisted/activities-agent-system")`
- Run pairwise A/B experiments when changing prompts to measure quality regression/improvement before rollout

---

## 4. Phased Development Roadmap

This roadmap is explicitly **learning-driven** — each phase teaches a reusable pattern you will recognise in hundreds of future systems.

---

### Phase 1 — Single-Agent Foundation (Weeks 1–2)

**Learning objective:** Master the core LangChain + LangGraph primitives: tools, ReAct loops, state, and tracing.

**What to build:**
- A single `TravelResearchAgent` that accepts a natural language request and returns a plain-text itinerary
- Use `MessagesState` as the state schema
- Bind `TavilySearch` and `WikipediaLoader` as tools
- Compile with `MemorySaver` for conversation history
- Enable LangSmith tracing from day one (`LANGSMITH_TRACING=true`)

**How it contributes:**
- You internalise the **ReAct loop pattern** (Reason → Act → Observe → Reason) that every future agent uses
- You understand how `add_messages` reducer and `MessagesState` work at the mechanical level
- You see in LangSmith traces exactly what the LLM is doing at each step

**Expected outcome:**
A working agent that can answer "What should I do in Kyoto for 3 days?" with a reasonable narrative — even if costs and bookings are absent.

**How to test/measure progress:**
- Manually evaluate 5 diverse travel requests
- Confirm every tool call appears in LangSmith traces
- Confirm conversation history persists across turns within a thread

---

### Phase 2 — Structured Outputs and Specialist Agents (Weeks 3–4)

**Learning objective:** Understand `with_structured_output`, Pydantic schemas, and building self-contained specialist agents.

**What to build:**
- `WeatherAgent`, `CurrencyAgent`, and `SafetyAgent` (the three simplest specialists)
- Define `DayWeather`, `CurrencyResult`, and `SafetyReport` as Pydantic models
- Each agent is a single-node graph with `with_structured_output` forcing validated JSON
- All three agents are individually testable in isolation
- Begin creating your LangSmith golden dataset with 10 test cases

**How it contributes:**
- You learn that **structured output is the key interface contract** between agents — it's what makes composition possible
- You see how Pydantic validation catches hallucinated or malformed data before it corrupts downstream agents
- You practice designing clean input/output schemas, which is the hardest design skill in multi-agent systems

**Expected outcome:**
Three independently callable agents that return validated, typed Python objects. A 10-example LangSmith dataset. First automated evaluation run.

**How to test/measure progress:**
- All three agents pass Pydantic schema validation on 20 test inputs
- LangSmith `evaluate()` runs successfully against the golden dataset
- Portfolio: can you predict what parameters each agent needs before writing code?

---

### Phase 3 — Multi-Agent Orchestration with Supervisor (Weeks 5–7)

**Learning objective:** Build a supervisor-routed multi-agent graph, manage shared state, and handle fan-in/fan-out parallelism.

**What to build:**
- Add `FlightSearchAgent` and `HotelSearchAgent` (with IATA lookup tool)
- Build the `TravelSupervisorGraph` with `TravelState`
- Implement the parallel fan-out (5 agents simultaneously) and fan-in (ActivitiesAgent waits for all)
- Implement `ActivitiesAgent` as a sub-graph with its own `ActivitiesState`
- Implement `BudgetAgent` as the final fan-in aggregation node
- Wire `ItineraryAssemblerAgent` as the final synthesis step

**How it contributes:**
- You learn the **supervisor pattern** — the single most reusable orchestration pattern in multi-agent systems
- You learn how `Annotated` reducers prevent `InvalidUpdateError` in parallel branches
- You experience the **emergent behaviour** that happens when agents pass structured data to each other
- You understand when sub-graphs are justified (ActivitiesAgent) vs. overkill (CurrencyAgent)

**Expected outcome:**
End-to-end generation of a structured travel plan (all sections, validated costs, day-by-day activities) for any major city. Parallel agents reducing total latency to under 30 seconds.

**How to test/measure progress:**
- Measure wall-clock latency: sequential baseline vs. parallel execution (expect 3–5x speedup)
- LangSmith trace must show all 5 parallel agents as sibling spans
- Budget accuracy evaluator passes on 80% of golden dataset examples

---

### Phase 4 — Human-in-the-Loop, Safety, and State Editing (Weeks 8–10)

**Learning objective:** Implement approval workflows, dynamic breakpoints, and state editing — the patterns that make agents safe in production.

**What to build:**
- Add `interrupt_before=["flight_booking_action"]` gate before any external write
- Implement `interrupt()` inside SupervisorNode to alert user when safety advisory is "do not travel"
- Implement `interrupt()` when budget is overspent by >$500 with three alternative scenarios
- Build a `HumanFeedbackNode` that allows the user to edit the analyst-generated day plans before final assembly
- Add time travel demo: show how to fork execution from a saved checkpoint to try an alternative destination

**How it contributes:**
- You internalise the principle: **agents that touch the real world must have human gates**
- You learn that `update_state()` + `as_node=` is how you inject external context into a running graph
- You see how checkpointers make graphs **auditable and reversible** — critical for production trust

**Expected outcome:**
A full conversation-style agent that pauses at key decisions, accepts user corrections, and never books anything without confirmation. LangSmith traces show interrupt events clearly.

**How to test/measure progress:**
- Manually walk through 3 scenarios: budget overrun, safety advisory, user modifies itinerary
- Confirm via `graph.get_state_history()` that all checkpoints are present and replayable
- Confirm payment credentials never appear in any LangSmith trace

---

### Phase 5 — Long-Term Memory, Deployment, and Production Monitoring (Weeks 11–14)

**Learning objective:** Add user profiles, cross-session memory, deploy to LangGraph Cloud, and set up production evaluation / online monitoring with LangSmith.

**What to build:**
- Integrate `InMemoryStore` (or `PostgresStore` in production) to store user travel profiles: preferred airlines, dietary restrictions, past trips, loyalty numbers
- Implement a `MemoryAgent` that reads/writes profile data and injects it into the supervisor's `user_context_node`
- Deploy the graph to LangGraph Cloud (or self-hosted via Docker) with `langgraph.json` config
- Integrate with LangGraph Agent Chat UI for a live demo
- Set up LangSmith online evaluation rules: flag any run where the handbook is missing a required section; alert on latency > 60 seconds
- Run pairwise A/B experiments: two versions of the `ActivitiesAgent` system prompt — evaluate which produces higher user satisfaction scores

**How it contributes:**
- You learn the **full LangGraph lifecycle**: from notebook prototype to deployed cloud service
- You understand the difference between short-term memory (checkpointer) and long-term memory (store) — one of the most misunderstood distinctions in agentic systems
- You experience LangSmith as a **production reliability tool**, not just a development debugger

**Expected outcome:**
A fully deployed, streamed, stateful travel agent that remembers user preferences across sessions, can be monitored in real time, and can be improved via systematic prompt experiments.

**How to test/measure progress:**
- Cross-session memory: user says "same airlines as last trip" — agent retrieves without re-asking
- LangGraph Cloud deployment: generate itinerary via SDK client, not just local `graph.invoke()`
- Production monitoring: one LangSmith alert rule fires correctly on a deliberately malformed test input

---

## 5. Itinerary Output — Comprehensive Specification

> **Goal:** Transform raw agent outputs (text blobs from 9+ agents) into a polished, interactive, data-rich travel handbook that feels like a premium product — not an LLM dump. Every piece of data the tools already fetch should surface visually.

---

### 5.1 What the Japan Handbook Got Right

The `outputs/japan_itinerary_v2.html` demonstrates genuine craft: tabbed navigation, print-safe CSS, embedded Google Maps, day cards with hover effects, highlighted cultural experiences, a phrasebook table, and a memorable "Special Moment" proposal section. The visual design language (red accent `#e41e3f`, card shadows, responsive max-width) is coherent and pleasant. These strengths are carried forward.

---

### 5.2 Gap Analysis — Available Data vs. What Gets Rendered

The current tools already fetch far more data than the output consumes. This table maps every API field to its intended role in the new handbook.

| API / Tool | Data fields **already fetched** but **not rendered** | New output role |
|---|---|---|
| **Google Places (activities.py)** | `photos[]` (photo URLs), `currentOpeningHours`, `editorialSummary`, `websiteUri`, `googleMapsUri`, `priceLevel` | Photo carousel per activity card; "Open now" badge; price $–$$$$ pill; one-tap Google Maps deep link |
| **Google Maps — Directions** | Step-by-step directions with transit line names, vehicle types | Per-day collapsible "Getting Around" panel with transit icons & walking/driving time between stops |
| **Google Maps — Distance Matrix** | Origin→destination duration/distance pairs | Visual proximity badges on day cards ("12 min walk from hotel"), inter-city transit time in route bar |
| **Google Maps — Route Optimisation** | `optimizedIntermediateWaypointIndex`, per-leg distance/duration | Auto-sequenced day plan (stops reordered for minimal backtracking); total walking km per day |
| **Duffel Flights** | Carrier code, flight #, segment details, layover info, baggage policy hints | Multi-segment flight timeline (visual bar); layover duration callout; carrier logo via Logo API |
| **Hotelbeds Hotels** | Room type (beds, bed type, category), check-in/check-out, full offer JSON | Room-type pill, bed icon, policy summary (cancellation, breakfast included) |
| **OpenWeatherMap** | 3-hourly raw data (aggregated to daily) | Hourly mini-chart on day cards; "best time to visit outdoor activity" note |
| **REST Countries (safety.py)** | Languages, currency name + symbol, timezones, population | Language badge in header; currency quick-ref sticky bar; timezone diff from origin |
| **ExchangeRate API** | Rate + last-updated timestamp | Live conversion widget in budget tab; "your $1 = ¥XXX" quick reference |
| **Pinecone RAG** | Section names, relevance scores, chunked guide text | Cultural tips injected contextually into the day they're relevant to (e.g., shrine etiquette on temple-visit day) |
| **Budget Calculator** | `BudgetBreakdown` (itemised Pydantic model) | Per-day micro-budget tracker + cumulative running total chart |

---

### 5.3 Structured Output Models (New Pydantic Schemas)

Before the handbook can be template-rendered, every agent must return structured data — not free text. Define these in `src/models/`:

```python
# src/models/itinerary.py

class FlightSegment(BaseModel):
    carrier: str                        # "NH" → resolved to "ANA"
    flight_number: str                  # "NH 110"
    departure_airport: str              # "JFK"
    arrival_airport: str                # "NRT"
    departure_time: datetime            # 2026-04-10T11:00
    arrival_time: datetime              # 2026-04-11T14:30
    duration_minutes: int               # 930
    cabin_class: str = "economy"
    stops: int = 0

class FlightOption(BaseModel):
    outbound: list[FlightSegment]       # multi-segment for layovers
    inbound: list[FlightSegment]
    total_price_usd: float
    currency: str = "USD"
    booking_url: str = ""               # deep link if available

class HotelOption(BaseModel):
    name: str
    star_rating: int                    # 1–5
    neighbourhood: str
    price_per_night_usd: float
    total_price_usd: float
    room_type: str                      # "Deluxe King"
    bed_type: str                       # "1 King Bed"
    check_in: date
    check_out: date
    amenities: list[str] = []           # ["WiFi", "Pool", "Breakfast"]
    cancellation_policy: str = ""
    booking_url: str = ""
    latitude: float = 0.0
    longitude: float = 0.0

class PlaceCard(BaseModel):
    """Unified model for activities, restaurants, and attractions."""
    name: str
    category: str                       # "temple", "ramen", "museum"
    rating: float | None = None
    review_count: int = 0
    price_level: str = ""               # "$", "$$", "$$$", "$$$$"
    address: str = ""
    description: str = ""               # editorialSummary
    website_url: str = ""
    google_maps_url: str = ""
    photo_urls: list[str] = []          # up to 3 photo URLs
    opening_hours: list[str] = []       # ["Mon: 9:00–17:00", ...]
    latitude: float = 0.0
    longitude: float = 0.0
    estimated_cost_usd: float = 0.0     # per-person estimate
    estimated_duration_minutes: int = 60

class TransitStep(BaseModel):
    mode: str                           # "walk", "transit", "drive"
    from_place: str
    to_place: str
    distance_text: str                  # "1.2 km"
    duration_text: str                  # "14 min"
    transit_line: str = ""              # "JR Yamanote Line"
    instructions: str = ""              # turn-by-turn summary

class DayWeather(BaseModel):
    date: date
    condition: str                      # "Partly Cloudy"
    emoji: str                          # "⛅"
    temp_low_c: float
    temp_high_c: float
    rain_probability_pct: int
    sunrise: str = ""
    sunset: str = ""
    uv_index: int = 0
    packing_tip: str = ""               # "Bring a light rain jacket"

class TimeBlock(BaseModel):
    """A single block within a day (morning/afternoon/evening)."""
    period: str                         # "morning", "afternoon", "evening"
    activities: list[PlaceCard]
    restaurant: PlaceCard | None = None
    transit: list[TransitStep] = []     # how to get between stops
    subtotal_usd: float = 0.0

class DayPlan(BaseModel):
    day_number: int
    date: date
    city: str
    weather: DayWeather
    time_blocks: list[TimeBlock]
    cultural_tip: str = ""              # RAG-injected contextual tip
    daily_cost_usd: float = 0.0
    walking_km: float = 0.0            # total walking for the day
    optimised_stop_order: list[str] = [] # from Route Optimisation API

class SafetyInfo(BaseModel):
    advisory_level: str                 # "green", "yellow", "orange", "red"
    advisory_summary: str
    visa_requirements: str
    health_requirements: list[str]      # ["Hepatitis A vaccine recommended"]
    emergency_numbers: dict[str, str]   # {"Police": "110", "Ambulance": "119"}
    languages: list[str]
    currency_name: str
    currency_symbol: str
    currency_code: str
    timezones: list[str]
    seasonal_risks: list[str] = []

class CultureGuide(BaseModel):
    phrases: list[dict[str, str]]       # [{"english": "Thank you", "local": "ありがとう", "romanized": "Arigatō"}]
    etiquette_tips: list[str]
    tipping_guide: str
    dining_customs: list[str]
    religious_customs: list[str] = []
    dress_code_notes: list[str] = []

class PackingItem(BaseModel):
    item: str
    reason: str                         # "Rainy days 3, 5, 7"
    category: str                       # "clothing", "documents", "tech", "health"
    essential: bool = True

class TripHandbook(BaseModel):
    """Top-level structured output — the complete handbook data."""
    # Header
    trip_title: str                     # "10 Days in Japan"
    traveller_names: list[str]
    origin_city: str
    destinations: list[str]
    start_date: date
    end_date: date
    total_budget_usd: float
    travel_style: str                   # "mid-range"
    group_type: str                     # "couple"
    dietary_restrictions: list[str] = []
    accessibility_needs: list[str] = []

    # Route
    route_cities: list[str]             # ["New York", "Tokyo", "Kyoto", "Osaka", "New York"]
    route_transport: list[str]          # ["flight", "shinkansen", "train", "flight"]

    # Core content
    flights: list[FlightOption]
    hotels: list[HotelOption]
    days: list[DayPlan]
    budget: BudgetBreakdown             # existing model
    safety: SafetyInfo
    culture: CultureGuide
    packing: list[PackingItem]

    # Metadata
    exchange_rate: float                # 1 USD = X local
    local_currency_code: str
    theme_accent_color: str = "#e41e3f" # CSS colour, destination-driven
    generated_at: datetime
    langsmith_run_id: str = ""
```

**Key design decision:** Every agent's structured output feeds `TripHandbook`. The assembler template never needs to parse free text.

---

### 5.4 Proposed Handbook Structure (Sections & Wireframe)

```
outputs/
  handbook.html           ← Primary output (rich, interactive, print-safe)
  handbook.md             ← Markdown fallback (paste into Notion/Obsidian)
  handbook.json           ← Machine-readable TripHandbook dump
  handbook.pdf            ← Auto-generated via weasyprint (optional)
```

**HTML Handbook Layout:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  HERO HEADER                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  "10 Days in Japan"                                             ││
│  │  April 10–20, 2026 · 2 travellers · Mid-range · $4,000 budget  ││
│  │  🇯🇵 Japanese · ¥ Yen · UTC+9 (13h ahead of EST)               ││
│  │  💱 $1 USD = ¥153.42 (as of Mar 31, 2026)                      ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  SAFETY BANNER (sticky, colour-coded by advisory level)             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 🟢 Japan — Level 1: Exercise Normal Precautions · Visa-free  │   │
│  │    90 days · No special vaccinations required                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  INTERACTIVE ROUTE BAR                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ NYC ✈──12h30──▶ Tokyo ──🚄 2h15──▶ Kyoto ──🚃 50m──▶ Osaka │   │
│  │                              ──✈──11h45──▶ NYC              │   │
│  │  [Distance Matrix durations injected from Google APIs]       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TAB 1: 📅 ITINERARY  (default view)                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  DAY 1 — Thu, Apr 10 · Tokyo                    [expand ▾]  │    │
│  │  ┌───────────────────────────────────────────────────────┐  │    │
│  │  │ WEATHER: ⛅ 14–21°C · 20% rain · UV 5                │  │    │
│  │  │ PACKING TIP: "Light layers; bring a compact umbrella" │  │    │
│  │  └───────────────────────────────────────────────────────┘  │    │
│  │                                                              │    │
│  │  🌅 MORNING                                                  │    │
│  │  ┌───────────────────────────────────────────────────────┐  │    │
│  │  │ ✈ Arrive NRT 14:30 · Transfer to hotel               │  │    │
│  │  │  └─ 🚃 Narita Express → Shinjuku (80 min, ¥3,250)    │  │    │
│  │  │     [Step-by-step from Directions API]                │  │    │
│  │  └───────────────────────────────────────────────────────┘  │    │
│  │                                                              │    │
│  │  🌆 AFTERNOON                                                │    │
│  │  ┌─────────────────────────────┐┌────────────────────────┐  │    │
│  │  │ [PHOTO]                     ││ Meiji Shrine            │  │    │
│  │  │ places.photos[0]            ││ ⭐ 4.6 (12,340 reviews) │  │    │
│  │  │ (Google Places Photo URL)   ││ 🏷 Free · ⏱ 90 min     │  │    │
│  │  │                             ││ 📍 1-1 Yoyogikamizonocho│  │    │
│  │  │                             ││ 🕐 Open: 05:00–18:00   │  │    │
│  │  │                             ││ 🚶 12 min from hotel    │  │    │
│  │  │                             ││ [📍 Maps] [🌐 Website]  │  │    │
│  │  └─────────────────────────────┘└────────────────────────┘  │    │
│  │                                                              │    │
│  │  🌙 EVENING                                                  │    │
│  │  ┌─────────────────────────────┐┌────────────────────────┐  │    │
│  │  │ [PHOTO]                     ││ 🍽 Ichiran Ramen         │  │    │
│  │  │ restaurant photo            ││ ⭐ 4.3 · $$ · Ramen     │  │    │
│  │  │                             ││ ~$12 per person          │  │    │
│  │  │                             ││ 🕐 Open: 24 hours       │  │    │
│  │  │                             ││ 🚶 5 min walk           │  │    │
│  │  │                             ││ ⚠ Dietary: ✓ available  │  │    │
│  │  └─────────────────────────────┘└────────────────────────┘  │    │
│  │                                                              │    │
│  │  💡 CULTURAL TIP (from RAG):                                 │    │
│  │  "At Meiji Shrine, bow once before entering the torii gate.  │    │
│  │   Walk on the sides — the centre path is for the deity."     │    │
│  │                                                              │    │
│  │  📊 DAY COST: $85 USD (¥13,023) · 🚶 4.2 km walked          │    │
│  │  📈 Running total: $285 / $4,000 (7.1% of budget)           │    │
│  │                                                              │    │
│  │  ▸ GETTING AROUND (collapsible)                              │    │
│  │  ┌───────────────────────────────────────────────────────┐  │    │
│  │  │ Hotel → Meiji Shrine: 🚶 12 min (0.9 km)             │  │    │
│  │  │ Meiji Shrine → Harajuku: 🚶 5 min (0.3 km)           │  │    │
│  │  │ Harajuku → Ichiran Shibuya: 🚃 8 min (JR Yamanote)   │  │    │
│  │  │ Ichiran → Hotel: 🚶 7 min (0.5 km)                   │  │    │
│  │  │ [Optimised order by Google Route Optimisation API]     │  │    │
│  │  └───────────────────────────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│  (repeats for each day)                                             │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TAB 2: ✈ FLIGHTS & TRANSPORT                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  OUTBOUND — Apr 10                                            │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  [Carrier Logo]  ANA NH 110                             │  │   │
│  │  │  JFK 11:00 ————————————— 14:30+1 NRT                  │  │   │
│  │  │  ⏱ 13h 30m · Economy · Non-stop                        │  │   │
│  │  │  💰 $892 USD per person                                 │  │   │
│  │  │  🧳 2×23kg checked + 7kg carry-on                      │  │   │
│  │  │  [Visual flight timeline bar]                           │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  RETURN — Apr 20                                              │   │
│  │  (same layout)                                                │   │
│  │                                                               │   │
│  │  INTER-CITY TRANSPORT                                         │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  🚄 Tokyo → Kyoto · Shinkansen Nozomi                  │  │   │
│  │  │  Apr 14 · 08:33 → 10:48 · 2h 15m · ¥13,320 (~$87)    │  │   │
│  │  │  [Visual route bar with intermediate stops]             │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  AIRPORT TRANSFERS (from Directions API)                      │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  NRT → Hotel Gracery Shinjuku                           │  │   │
│  │  │  Option A: 🚃 Narita Express · 80 min · ¥3,250         │  │   │
│  │  │  Option B: 🚌 Airport Limousine · 100 min · ¥3,200     │  │   │
│  │  │  Option C: 🚕 Taxi · 60–90 min · ¥20,000+              │  │   │
│  │  │  [Step-by-step directions expandable]                   │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  TRANSPORT PASSES & TIPS (from RAG)                           │   │
│  │  • JR Pass (7-day): ¥50,000 — worth it for Tokyo→Kyoto+     │   │
│  │  • IC Card (Suica/Pasmo): tap-and-go for trains, buses,      │   │
│  │    vending machines. Get at any station.                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TAB 3: 🏨 HOTELS                                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  For each hotel:                                              │   │
│  │  ┌────────┐ Hotel Gracery Shinjuku ★★★★                     │   │
│  │  │ [MAP]  │ 📍 Kabukicho, Shinjuku                           │   │
│  │  │ embed  │ 🛏 Deluxe Twin · 2 beds                          │   │
│  │  │        │ 📅 Apr 10–14 (4 nights) · $140/night             │   │
│  │  │        │ 💰 Total: $560 USD                                │   │
│  │  │        │ ✅ WiFi · 🍳 Breakfast · 🏊 Pool · ♿ Accessible  │   │
│  │  │        │ 📋 Free cancellation until Apr 8                  │   │
│  │  │        │ [🔗 Book Now]                                     │   │
│  │  └────────┘                                                   │   │
│  │                                                               │   │
│  │  NEIGHBOURHOOD OVERVIEW MAP (Google Maps embed)               │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │ Embedded map with hotel pin + nearby restaurant/       │  │   │
│  │  │ attraction pins from Places API (lat/lng data)         │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TAB 4: 💰 BUDGET SUMMARY                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  BUDGET OVERVIEW                                              │   │
│  │  ┌──────────────────────────────────────────────┐            │   │
│  │  │  Total Budget: $4,000 · Estimated: $3,420     │            │   │
│  │  │  Remaining: $580 (14.5%) ← green bar          │            │   │
│  │  │  Per person: $1,710                            │            │   │
│  │  └──────────────────────────────────────────────┘            │   │
│  │                                                               │   │
│  │  CATEGORY BREAKDOWN (CSS-only stacked bar chart)              │   │
│  │  ┌──────────────────────────────────────────────┐            │   │
│  │  │ ✈ Flights      $1,784  52.2%  ████████████▏  │            │   │
│  │  │ 🏨 Hotels       $  980  28.7%  ███████▏      │            │   │
│  │  │ 🍽 Meals        $  320   9.4%  ██▍           │            │   │
│  │  │ 🎯 Activities   $  150   4.4%  █▏            │            │   │
│  │  │ 🚃 Transport    $  106   3.1%  ▊             │            │   │
│  │  │ 📦 Misc         $   80   2.3%  ▌             │            │   │
│  │  │ ────────────────────────────────              │            │   │
│  │  │ 💰 TOTAL       $3,420 100.0%                  │            │   │
│  │  └──────────────────────────────────────────────┘            │   │
│  │                                                               │   │
│  │  DAILY SPENDING TRACKER (running total)                       │   │
│  │  ┌──────────────────────────────────────────────┐            │   │
│  │  │  Day 1: $85 · Day 2: $120 · Day 3: $95 ...   │            │   │
│  │  │  [Sparkline / mini bar chart per day]          │            │   │
│  │  │  [Cumulative line graph vs. budget ceiling]    │            │   │
│  │  └──────────────────────────────────────────────┘            │   │
│  │                                                               │   │
│  │  CURRENCY QUICK-REFERENCE                                     │   │
│  │  ┌──────────────────────────────────────────────┐            │   │
│  │  │  💱 $1 USD = ¥153.42 (from ExchangeRate API)  │            │   │
│  │  │  Common amounts: $10 = ¥1,534 · $50 = ¥7,671  │            │   │
│  │  │  💳 Cards accepted widely in cities            │            │   │
│  │  │  💴 Cash needed for: shrines, small shops,     │            │   │
│  │  │     vending machines, some restaurants          │            │   │
│  │  │  🏧 7-Eleven ATMs accept international cards   │            │   │
│  │  └──────────────────────────────────────────────┘            │   │
│  │                                                               │   │
│  │  OVER-BUDGET RECOVERY (conditional — shown only if needed)    │   │
│  │  "You're $220 (5.5%) over budget. Suggestions:               │   │
│  │   • Switch hotel nights 5–7 to a 3★ ($80 saved)             │   │
│  │   • Replace taxi Day 3 with metro ($35 saved)                │   │
│  │   • Skip Teamlab Borderless ($32/person saved)"              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TAB 5: 🗺 MAPS & ROUTES                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  PER-CITY INTERACTIVE MAP (Google Maps embed)                 │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │ Embedded Google Map with markers for:                   │  │   │
│  │  │  🔵 Hotel    🔴 Attractions    🟢 Restaurants           │  │   │
│  │  │  🟡 Transport hubs                                      │  │   │
│  │  │  All lat/lng from Places API + Hotels API               │  │   │
│  │  │  Clickable markers → link to Google Maps deep link      │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  PER-DAY ROUTE MAP                                            │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  Day 1 Route (from Route Optimisation API):             │  │   │
│  │  │  Hotel → Meiji Shrine → Harajuku → Shibuya Crossing    │  │   │
│  │  │       → Ichiran Ramen → Hotel                           │  │   │
│  │  │  Total: 6.2 km · 🚶 4.2 km walking + 🚃 2.0 km train  │  │   │
│  │  │  [Google Maps Directions embed with polyline]           │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  GETTING THERE OVERVIEW                                       │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  [Distance Matrix output — all inter-city pairs]        │  │   │
│  │  │  Tokyo ↔ Kyoto: 🚄 2h15m (476 km)                      │  │   │
│  │  │  Kyoto ↔ Osaka: 🚃 50m (43 km)                         │  │   │
│  │  │  Osaka ↔ KIX Airport: 🚃 70m (46 km)                   │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TAB 6: 🛡 SAFETY & HEALTH                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  ADVISORY (colour-coded card from REST Countries data)        │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │ 🟢 Level 1: Exercise Normal Precautions                 │  │   │
│  │  │ Japan is one of the safest travel destinations.         │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  ENTRY REQUIREMENTS                                           │   │
│  │  • Visa: Visa-free for US citizens (90 days)                  │   │
│  │  • Passport: Valid 6+ months beyond travel dates              │   │
│  │  • COVID: No requirements as of March 2026                    │   │
│  │                                                               │   │
│  │  HEALTH                                                       │   │
│  │  • No mandatory vaccinations                                  │   │
│  │  • Recommended: Hepatitis A, routine vaccines up to date      │   │
│  │  • Tap water is safe to drink throughout Japan                │   │
│  │  • Pharmacies (ドラッグストア): Matsumoto Kiyoshi everywhere  │   │
│  │                                                               │   │
│  │  EMERGENCY CONTACTS                                           │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  🚨 Police: 110 · 🚑 Ambulance/Fire: 119               │  │   │
│  │  │  🏥 English helpline: 03-5285-8181 (AMDA)              │  │   │
│  │  │  🇺🇸 US Embassy Tokyo: 03-3224-5000                    │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  NATURAL HAZARDS & SEASONAL RISKS                             │   │
│  │  • Earthquake-prone: know hotel evacuation routes             │   │
│  │  • Typhoon season: Jun–Oct (your April dates are safe)        │   │
│  │  • Download: Japan Official Travel App + NHK World for alerts │   │
│  │                                                               │   │
│  │  ACCESSIBILITY (conditional — shown when needs specified)     │   │
│  │  • Wheelchair access ratings per activity (from Places API)   │   │
│  │  • Accessible transit routes highlighted in day plans         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TAB 7: 🎌 CULTURE & LANGUAGE                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  PHRASEBOOK (from RAG — destination_guides)                   │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  English        │ Local          │ Romanized            │  │   │
│  │  │  Hello          │ こんにちは      │ Konnichiwa           │  │   │
│  │  │  Thank you      │ ありがとう      │ Arigatō              │  │   │
│  │  │  Excuse me      │ すみません      │ Sumimasen            │  │   │
│  │  │  How much?      │ いくらですか？  │ Ikura desu ka?       │  │   │
│  │  │  Where is...?   │ ...はどこですか│ ...wa doko desu ka?  │  │   │
│  │  │  Delicious!     │ おいしい！      │ Oishii!              │  │   │
│  │  │  Check please   │ お会計          │ O-kaikei             │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  ETIQUETTE (from RAG)                                         │   │
│  │  • 🏯 Shrines & Temples: Bow before entering, walk on sides  │   │
│  │  • 🍜 Dining: Slurping noodles is polite; no tipping         │   │
│  │  • 🚃 Transit: No phone calls on trains; offer seats          │   │
│  │  • 👞 Shoes: Remove at temples, ryokans, some restaurants     │   │
│  │  • 🎁 Gifts: Use both hands to give/receive                   │   │
│  │                                                               │   │
│  │  DIETARY GUIDE (conditional — shown for restrictions)         │   │
│  │  • "Vegetarian in Japan: look for shojin ryori (temple        │   │
│  │     cuisine). Warning: dashi stock contains bonito flakes."   │   │
│  │  • Restaurant cards with dietary icons (✓/✗ per restriction)  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TAB 8: 🧳 PACKING LIST (weather-driven + activity-aware)           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Auto-generated from DayWeather + activities + safety         │   │
│  │                                                               │   │
│  │  👔 CLOTHING (driven by temp range across all days)           │   │
│  │  ☑ Light layers (14–24°C expected)                            │   │
│  │  ☑ Compact rain jacket (rain on days 3, 5, 7)                │   │
│  │  ☑ Comfortable walking shoes (avg 5 km/day)                   │   │
│  │  ☑ Temple-appropriate: cover shoulders + knees                │   │
│  │                                                               │   │
│  │  📄 DOCUMENTS                                                 │   │
│  │  ☑ Passport (valid until Oct 2027 — ✓ OK)                    │   │
│  │  ☑ Travel insurance printout                                  │   │
│  │  ☑ Hotel confirmations (offline copy)                         │   │
│  │  ☑ Flight e-tickets                                           │   │
│  │                                                               │   │
│  │  📱 TECH                                                      │   │
│  │  ☑ Power adapter: Type A/B (same as US — no adapter needed)  │   │
│  │  ☑ Portable WiFi / eSIM (¥900/day at airport)                 │   │
│  │  ☑ Offline Google Maps for Tokyo, Kyoto, Osaka                │   │
│  │                                                               │   │
│  │  💊 HEALTH                                                    │   │
│  │  ☑ Personal medications                                       │   │
│  │  ☑ Motion sickness tablets (Shinkansen, if sensitive)         │   │
│  │                                                               │   │
│  │  💴 MONEY                                                     │   │
│  │  ☑ Cash: ¥30,000 for first 3 days (~$195)                    │   │
│  │  ☑ Credit card with no foreign transaction fees               │   │
│  │  ☑ IC card (buy at airport — rechargeable transit pass)       │   │
│  │                                                               │   │
│  │  🎌 ACTIVITIES-SPECIFIC                                       │   │
│  │  ☑ Socks without holes (shoe removal at temples!)             │   │
│  │  ☑ Small towel (onsen etiquette)                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  FOOTER                                                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Generated by Wanderlisted · March 31, 2026                   │   │
│  │  Powered by LangChain + LangGraph + LangSmith                │   │
│  │  🔗 LangSmith trace: https://smith.langchain.com/runs/abc123 │   │
│  │  📤 Export: [HTML] [Markdown] [JSON] [PDF]                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 5.5 New Features Powered by Google APIs

These features are **already possible** with the tools in `src/tools/` — they just need to be wired into the output:

#### 5.5.1 Activity Photo Cards (Google Places Photos)

The `search_activities` tool already fetches `photos[]` and builds URLs via `_photo_url()`. Surface these as visual cards:

```html
<!-- Activity card with Places API photo -->
<div class="activity-card">
  <img src="{{ activity.photo_urls[0] }}"
       alt="{{ activity.name }}"
       loading="lazy"
       class="activity-photo" />
  <div class="activity-info">
    <h4>{{ activity.name }}</h4>
    <span class="rating-pill">⭐ {{ activity.rating }}/5 ({{ activity.review_count }} reviews)</span>
    <span class="price-pill">{{ activity.price_level }}</span>
    <p class="description">{{ activity.description[:150] }}</p>
    <div class="hours">🕐 {{ activity.opening_hours[0] if activity.opening_hours else "Hours not listed" }}</div>
    <div class="action-links">
      <a href="{{ activity.google_maps_url }}" target="_blank">📍 Open in Maps</a>
      <a href="{{ activity.website_url }}" target="_blank">🌐 Website</a>
    </div>
  </div>
</div>
```

#### 5.5.2 Per-Day Route Optimisation (Google Routes API)

The `optimize_day_route` tool already returns optimal stop ordering. Show this in each day card:

```
Original order: Hotel → Tokyo Tower → Senso-ji → Meiji Shrine → Imperial Palace
Optimised:      Hotel → Meiji Shrine → Imperial Palace → Senso-ji → Tokyo Tower
                Saves 45 min + 3.2 km of backtracking
```

Visualise as a numbered route with distance/duration between each stop.

#### 5.5.3 Transit Directions Panel (Google Routes API)

The `compute_route` tool returns step-by-step directions with transit line names and vehicle types (set `include_steps=True`, `travel_mode="TRANSIT"`). Render as a collapsible panel per day:

```
🚶 Walk 3 min to Shinjuku Station (South Exit)
🚃 JR Yamanote Line → Harajuku (2 stops, 4 min)
🚶 Walk 8 min to Meiji Shrine entrance
```

#### 5.5.4 Proximity Badges

The `compute_route` tool computes hotel-to-attraction distances (call once per destination). Show as badges:

```
🏨→🏯 Meiji Shrine: 12 min walk
🏨→🗼 Tokyo Tower: 25 min by transit
🏨→⛩ Senso-ji: 35 min by transit
```

#### 5.5.5 Neighbourhood Maps with Multi-Marker Embeds

Using lat/lng from Places API and Hotels API, build Google Maps Static API or embed URLs with all markers for a given city/day:

```html
<iframe
  src="https://www.google.com/maps/embed/v1/place?key={{ api_key }}&q={{ hotel.latitude }},{{ hotel.longitude }}&zoom=14"
  loading="lazy"
  class="neighbourhood-map">
</iframe>
```

For richer multi-marker maps, use a Static Maps URL with custom markers:

```
https://maps.googleapis.com/maps/api/staticmap?
  size=800x400&
  markers=color:blue|label:H|{{ hotel.lat }},{{ hotel.lng }}&
  markers=color:red|label:1|{{ activity1.lat }},{{ activity1.lng }}&
  markers=color:red|label:2|{{ activity2.lat }},{{ activity2.lng }}&
  markers=color:green|label:R|{{ restaurant.lat }},{{ restaurant.lng }}&
  key={{ api_key }}
```

---

### 5.6 Design System

| Element | Current | New |
|---|---|---|
| Theme colour | Hard-coded `#e41e3f` | CSS variable `--accent` auto-set by destination: cherry-blossom pink (Japan), terracotta (Italy), ocean teal (Greece), desert gold (Morocco), sage green (New Zealand) |
| Typography | System font | Google Fonts: `Inter` 400/500/600 (body) + `Playfair Display` 700 (headings) |
| Day weather | Absent | Weather badge pill: emoji + temp range + rain % + UV index. Colour: blue (cold), amber (warm), red (hot) |
| Budget tracking | Aggregate only | Colour-coded: 🟢 under budget (>10% remaining), 🟡 tight (<10% remaining), 🔴 over budget. Running total sparkline chart |
| Safety banner | Absent | Sticky top banner, auto-coloured by advisory level |
| Activity cards | Text only | Photo + metadata card (rating, price, hours, maps link, description) from Places API |
| Transit directions | Absent | Collapsible per-day panel with mode icons (🚶🚃🚕), transit line names, durations |
| Route maps | Static embeds | Per-day route maps with numbered markers + polyline from Route Optimisation |
| Print layout | Partial | Full print stylesheet: page breaks between days, force all tabs inline, hide interactive elements, generate QR codes for booking links |
| Mobile | Partially responsive | Mobile-first: tabs → accordion, photo cards → swipeable carousel, maps → lazy-loaded, sticky budget bar at bottom |
| Accessibility | None | WCAG 2.1 AA: ARIA labels, `role="tablist"`, keyboard navigation, `prefers-reduced-motion`, `prefers-color-scheme: dark`, minimum 4.5:1 contrast ratios |
| Dark mode | None | `@media (prefers-color-scheme: dark)` with adjusted palette, reduced-brightness photos, dark map tiles |
| Dietary indicators | Not shown | Per-restaurant icons: 🥬 vegetarian, 🌾 gluten-free, ☪ halal, 🕐 kosher — based on `dietary_restrictions` from user profile |
| Proximity badges | Not shown | "12 min walk from hotel" on each activity card, from Routes API |

---

### 5.7 Generation Pipeline

```
TravelAgentState (accumulated agent outputs)
        │
        ▼
  ┌─────────────────────────────────┐
  │  StructuredOutputParser          │  Each agent returns Pydantic models
  │  - FlightsAgent → FlightOption   │  (via llm.with_structured_output)
  │  - HotelsAgent → HotelOption     │
  │  - ActivitiesAgent → PlaceCard   │
  │  - WeatherAgent → DayWeather     │
  │  - etc.                          │
  └────────────┬────────────────────┘
               │
               ▼
  ┌─────────────────────────────────┐
  │  ItineraryAssemblerAgent         │  Pure synthesis node (no API calls)
  │  1. Validate all structured data │
  │  2. Build TripHandbook model     │
  │  3. Select destination theme     │
  │  4. Inject RAG cultural tips     │
  │     into relevant day cards      │
  │  5. Compute per-day costs        │
  │  6. Generate packing list from   │
  │     weather + activities data    │
  └────────────┬────────────────────┘
               │
               ▼
  ┌─────────────────────────────────┐
  │  TemplateRenderer                │  Jinja2 template engine
  │  - handbook_template.html.j2     │
  │  - Renders TripHandbook → HTML   │
  │  - Inlines all CSS (single-file) │
  │  - Photo URLs → <img> tags       │
  │  - lat/lng → map embeds          │
  │  - Transit steps → route panels  │
  └────────────┬────────────────────┘
               │
               ├──► handbook.html     (primary deliverable)
               ├──► handbook.md       (via markdownify — Notion/Obsidian ready)
               ├──► handbook.json     (json.dumps(TripHandbook.model_dump()))
               └──► handbook.pdf      (optional — via weasyprint)
```

**Template location:** `src/agent/templates/handbook_template.html.j2`

**Key design decisions:**
- All CSS is **inlined** in a single `<style>` block — the HTML file must be fully self-contained and shareable as an email attachment
- Photos use `loading="lazy"` to avoid blocking initial render
- Maps use `loading="lazy"` on `<iframe>` elements
- Google Places photo URLs are **not cached** — they expire after a session, which is acceptable for a generated-once handbook
- The template uses **zero JavaScript dependencies** — only vanilla JS for tab switching and accordion toggles
- Print stylesheet uses `@media print` to force all tabs visible, hide interactive elements, and insert page breaks
- Markdown export strips HTML to clean Markdown via `markdownify` library (lightweight, no Pandoc dependency)

**New dependencies:**
```
jinja2>=3.1          # Template engine
markdownify>=0.13    # HTML → Markdown
weasyprint>=62       # HTML → PDF (optional, heavyweight)
```

---

### 5.8 Agent-to-Template Data Contract

Every field in the Jinja2 template maps to a specific agent and tool:

| Template section | Agent source | Tool(s) that produce the data | Structured model |
|---|---|---|---|
| Hero header | SupervisorAgent (user profile extraction) | — | `TripHandbook` top-level fields |
| Safety banner | DestinationAgent | `get_safety_info` (REST Countries) | `SafetyInfo` |
| Route bar | TransportationAgent | `compute_route` (Google Routes) | `route_cities` + `route_transport` |
| Day cards — activities | ActivitiesAgent | `search_activities` (Google Places) | `PlaceCard` (with `photo_urls`, `opening_hours`, `google_maps_url`) |
| Day cards — restaurants | RestaurantsAgent | `search_places_nearby`, `search_places_text` (Google Places) | `PlaceCard` (with dietary compatibility flags) |
| Day cards — weather | DestinationAgent | `get_weather` (OpenWeatherMap) | `DayWeather` |
| Day cards — transit | TransportationAgent | `compute_route` (Google Routes) | `TransitStep` |
| Day cards — route order | Transportation stage | `RoutePlan` from Google Routes | `DayRoute.ordered_stops` |
| Day cards — proximity | Transportation stage | `RoutePlan` from Google Routes | `RouteLeg.distance_meters` |
| Day cards — cultural tip | DestinationAgent | `search_destination_guides` (Pinecone RAG) | `DayPlan.cultural_tip` |
| Day cards — daily cost | BudgetAgent | `calculate_budget` | `DayPlan.daily_cost_usd` |
| Flights tab | FlightsAgent | `search_flights` (Duffel) | `FlightOption` + `FlightSegment` |
| Hotels tab | HotelsAgent | `search_hotels_hotelbeds` (Hotelbeds) | `HotelOption` |
| Budget tab | BudgetAgent | `calculate_budget`, `convert_currency` | `BudgetBreakdown` + exchange rate |
| Maps tab | Transportation stage | `compute_route`, typed route planner (Google Routes) | `DraftItinerary` place refs + `RoutePlan` |
| Safety tab | DestinationAgent | `get_safety_info`, RAG | `SafetyInfo` |
| Culture tab | DestinationAgent | RAG (`search_destination_guides`) | `CultureGuide` |
| Packing tab | ItineraryAssemblerAgent (derived) | Weather + activities + safety data | `PackingItem[]` |
| Currency reference | BudgetAgent | `convert_currency` (ExchangeRate API) | `TripHandbook.exchange_rate` |

---

### 5.9 Personalisation Hooks

User profile data (extracted by supervisor) should visibly affect the output:

| Profile field | How it changes the handbook |
|---|---|
| `travel_style = "budget"` | Budget tab shows saving tips prominently; hotels sorted by price ascending; activities prioritise free/cheap options |
| `travel_style = "luxury"` | Premium hotel photos featured; fine-dining restaurants highlighted; activities include exclusive experiences |
| `group_type = "family"` | Family-friendly activity badges; kid meal pricing; stroller-accessible transit routes; nap-time gaps in schedule |
| `group_type = "couple"` | Romantic restaurant picks highlighted; "Special Moment" section (like the Japan handbook); evening-weighted schedules |
| `dietary_restrictions = ["vegetarian"]` | Per-restaurant dietary compatibility icons; "Vegetarian guide for [country]" section from RAG; alert on restaurants with limited options |
| `accessibility_needs = ["wheelchair"]` | Transit directions prefer step-free routes; activities flag wheelchair accessibility; hotels show accessible room types |
| `traveller_names` | Names in hero header; personalised packing list ("Don't forget Sarah's medication") |

---

### 5.10 Export Formats

| Format | Method | Use case |
|---|---|---|
| **HTML** (primary) | Jinja2 render → single self-contained `.html` file | Share via email, open anywhere, print from browser |
| **Markdown** | `markdownify` conversion from HTML | Paste into Notion, Obsidian, Bear, Logseq |
| **JSON** | `TripHandbook.model_dump_json(indent=2)` | Machine-readable for downstream tools, re-import into Wanderlisted for edits |
| **PDF** | `weasyprint` (optional) | Offline reference, especially useful when travelling without connectivity |

All four formats are generated from the same `TripHandbook` Pydantic model — single source of truth.

---

## Architecture Patterns Captured Here (Reuse in Future Systems)

One of the goals of this document is to help you recognise patterns transferable to other domains. Here is a map:

| Pattern | Where Used Here | Where It Generalises |
|---|---|---|
| Supervisor-router | `TravelSupervisorGraph` routing between specialists | Any domain with multiple specialists: medical triage, legal discovery, e-commerce search |
| Fan-out / fan-in | 5 parallel agents feeding ActivitiesAgent | Parallel data gathering: competitive intelligence, portfolio analysis |
| Sub-graph encapsulation | `ActivitiesAgent` as nested graph | Any agent whose internal state must not pollute parent state |
| Structured output contracts | Every agent returns a Pydantic model | Anywhere two agents communicate — the schema IS the API |
| Human-in-the-loop gate | Before booking, before over-budget output | Any write to the real world: email sends, payments, database writes |
| Fault isolation reducers | `agent_errors: Annotated[list, add]` | Collecting partial failures without stopping the graph |
| LLM-as-Judge evaluation | Itinerary quality assessment | Any subjective output without a ground truth label |
| Cross-session memory store | User travel profile | Any system that should improve with repeated use: personal assistants, CRMs |
| Thread-scoped checkpointing | Per-user conversation history | Any conversational agent |
| LangSmith prompt versioning | Activities and safety prompts on Hub | Production systems where prompt quality is a first-class engineering concern |

---

Wanderlisted · March 2026*
