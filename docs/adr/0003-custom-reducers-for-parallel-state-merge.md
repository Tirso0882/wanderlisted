# 0003 — Custom state reducers for parallel fan-out merges

**Status:** Accepted · **Date:** 2026-07-10 (retroactively documented) · **Deciders:** Tirso Gomez

## Context

The parallel fan-out from [ADR-0001](0001-multi-agent-supervisor-parallel-fanout.md) dispatches six worker
nodes in the same super-step. Each worker writes back to **shared keys** in `TravelAgentState`:

- `itinerary_components` — each worker adds its own result, e.g. `{"flights": result}`.
- `current_agent` — each worker records which agent just ran.

LangGraph applies all updates from a super-step to the state. With the **default overwrite semantics** (last
write wins, one value per key per step), two workers writing the same key in one step raises:

```
InvalidUpdateError: Can receive only one value per step
```

This was discovered when all six agents completed their Azure OpenAI calls successfully but the graph crashed
on state write-back — the `itinerary_components` key already had a merge reducer, but `current_agent` did not
(captured in repo memory `current-agent-reducer`).

## Decision

Annotate every state key that parallel nodes can write with an explicit **reducer** in
[../../src/agent/state.py](../../src/agent/state.py):

- `itinerary_components: Annotated[dict, _merge_components]` — **shallow-merges** each worker's
  `{agent_name: result}` into the accumulated dict. Sequential nodes that spread `{**components, "key": v}`
  keep working because the reducer merges their full copy back in.
- `current_agent: Annotated[str, _last_value]` — a **last-writer-wins** reducer that simply accepts the new
  value, which makes concurrent writes legal.

## Consequences

**Positive**

- Parallel workers write structured results safely; no `InvalidUpdateError`.
- Sequential and parallel writers share the same keys without special-casing.
- Results are structured (`itinerary_components`) rather than only prose in `messages`.

**Negative / costs**

- **Footgun:** any *new* key a parallel node writes must get a reducer, or the graph crashes at runtime (not
  at build time). This is now called out in the project Copilot instructions and the DoD checklist.
- Shallow merge means two workers writing the *same* sub-key would still collide — safe here only because each
  worker owns a distinct key (its own agent name).

## Alternatives considered

| Alternative | Why rejected | When to choose it instead |
|-------------|--------------|---------------------------|
| **Private per-worker state + manual aggregation node** | More boilerplate; loses the natural "each worker owns its key" model | When workers must post-process each other's outputs before merge |
| **Write only to `messages` (add_messages reducer)** | Loses structured components needed by budget/itinerary/render | When downstream only needs conversational text |
| **Serialize the workers** | Defeats the parallelism from ADR-0001 | When true data dependencies exist between workers |

## References

- Code: [../../src/agent/state.py](../../src/agent/state.py) (`_merge_components`, `_last_value`, `TravelAgentState`)
- Code: [../../src/agent/stage4_graph.py](../../src/agent/stage4_graph.py) (`_run_parallel_agent` writes `{agent_name: result}`)
- Repo memory: `current-agent-reducer`, `parallel-agent-error-handling`
- Related: [ADR-0001](0001-multi-agent-supervisor-parallel-fanout.md)
