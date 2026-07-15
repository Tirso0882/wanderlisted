---
name: langgraph-stage4
description: 'Work safely inside the Wanderlisted Stage 4 multi-agent supervisor graph. WHEN editing stage4_graph.py, adding a graph node, adding or removing a parallel agent, Send fan-out, parallel agents do not merge, itinerary_components lost or overwritten, custom reducer, one agent crash takes down the whole graph, HITL interrupt / Command resume, safety_review / budget_review / human_review gate, triage or supervisor routing, build_context_messages, or wiring an agent into the primary graph.'
---

# Stage 4 Multi-Agent Graph

The primary runtime graph lives in
[src/agent/stage4_graph.py](../../../src/agent/stage4_graph.py) (~1500 lines).
`graph.py` and `agent.py` are **legacy** — do not modify them.

## Flow

`START → TRIAGE → (shallow_reply | SUPERVISOR)`. The supervisor uses `Send()` to
fan out **6 parallel workers** (flights, hotels, destination, restaurants,
activities, transportation) → fan-in → `SAFETY_REVIEW` → `BUDGET` →
`BUDGET_REVIEW` → `ITINERARY` → `HUMAN_REVIEW` → `RENDER_HANDBOOK → END`.

## Non-negotiable patterns

- **Every parallel worker must go through `_run_parallel_agent()`.** It catches
  exceptions and returns a graceful-degradation `AIMessage` plus
  `itinerary_components: {agent: {"error": ...}}` so one failing external API
  (Duffel, Hotelbeds, etc.) can never crash the whole pipeline. Never call a
  worker executor directly in a node.
- **Parallel results merge through a custom reducer.** Workers write to
  `itinerary_components` which shallow-merges concurrent `Send()` writes. If you
  return a plain dict without the reducer, concurrent writes clobber each other.
  Check the reducer wiring in [src/agent/state.py](../../../src/agent/state.py).
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
