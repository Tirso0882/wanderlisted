---
name: langgraph-stage4
description: 'Work safely inside the Wanderlisted Stage 4 multi-agent supervisor graph. WHEN editing stage4_graph.py, adding a graph node, adding or removing a parallel agent, Send fan-out, parallel agents do not merge, itinerary_components lost or overwritten, custom reducer, one agent crash takes down the whole graph, HITL interrupt / Command resume, safety_review / budget_review / human_review gate, triage or supervisor routing, build_context_messages, or wiring an agent into the primary graph.'
---

# Stage 4 Multi-Agent Graph

The primary runtime graph lives in
[src/agent/stage4_graph.py](../../../src/agent/stage4_graph.py) (~1500 lines).
`graph.py` and `agent.py` are **legacy** — do not modify them.

## Flow

`START → TRIAGE → (shallow_reply | INTAKE)`. Intake merges each turn into a
typed `TripRequest` and ends the turn with `needs_user_input` when required
fields are missing. The supervisor then uses `Send()` to fan out **4 initial
discovery workers** (flights, destination, restaurants, activities) → fan-in →
`COMPONENT_GATE` → `SAFETY_REVIEW` → `TRIP_SKELETON`. The skeleton selects exact
dates and allocates nights, then one `hotel_stay` worker per city searches
Hotelbeds → `HOTEL_GATE` → `DRAFT_ITINERARY` →
`TRANSPORTATION` → `BUDGET` → `BUDGET_REVIEW` → `ITINERARY` →
`HUMAN_REVIEW` → `RENDER_HANDBOOK → END`. Draft selection fixes exact hotel and
stop references; Transportation owns route computation and emits `RoutePlan`.

## Non-negotiable patterns

- **Every parallel worker must go through `_run_parallel_agent()`.** It catches
  exceptions and returns a typed `component_results` outcome plus the legacy
  transcript. The completion gate must stop dependent planning when a requested
  component needs input, has no inventory, is provider-blocked, or failed.
- **Parallel results merge through a custom reducer.** Workers write to
  `itinerary_components` which shallow-merges concurrent `Send()` writes. If you
  return a plain dict without the reducer, concurrent writes clobber each other.
  Check the reducer wiring in [src/agent/state.py](../../../src/agent/state.py).
- **Hotels must never run in initial discovery.** Hotelbeds requires exact city
  check-in/check-out dates and occupancy. It runs only from `TripSkeleton` via
  per-stay `Send()` workers and merges through `hotel_search_results`.
- **Read state with `.get("field", default)`** — `TravelAgentState` is a
  TypedDict, never use attribute access.
- **Read any LLM reply via `_extract_text_content(msg.content)`** — content is a
  Responses-API block list, not a string (see the `responses-api-reasoning` skill).
- **HITL gates use `interrupt()` to pause and `Command(resume=...)` to continue.**
  safety_review (do-not-travel/red advisory), budget_review (overspend), and
  human_review (final approval) are the three gates.

## Adding a new parallel agent (full checklist)

1. Create the agent class extending `SpecializedAgent` in `src/agent/agents/`.
2. Register it in `src/agent/agents/__init__.py`.
3. Add its name to `VALID_AGENT_NAMES` in `supervisor_agent.py`.
4. Add it to the supervisor prompt in `src/agent/prompts/agent_prompt.py`.
5. Add a node that delegates to `_run_parallel_agent(...)` and wire the `Send()`
   fan-out + fan-in edge in `stage4_graph.py`.

Miss any step and the agent silently never runs, or the supervisor routes to a
name the graph does not have.

## Source of truth / verify against

- Error-resilient worker wrapper: `_run_parallel_agent()` in [src/agent/stage4_graph.py](../../../src/agent/stage4_graph.py)
- State shape + reducers: [src/agent/state.py](../../../src/agent/state.py)
- Valid agent names: `VALID_AGENT_NAMES` in `src/agent/agents/supervisor_agent.py`
