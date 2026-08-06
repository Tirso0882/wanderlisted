# 0001 — Multi-agent supervisor with parallel `Send()` fan-out

**Status:** Accepted · **Date:** 2026-07-10 (retroactively documented; decided during Stage 4) · **Deciders:** Tirso Gomez

## Context

Wanderlisted grew from a single ReAct agent (Stages 1–3) into a system with **8 specialist agents**
(flights, hotels, destination, restaurants, activities, transportation, budget, itinerary). Three forces
shaped the coordination design:

1. **Independence:** six of the data-gathering tasks (flights, hotels, destination, restaurants, activities,
   transportation) share no data with one another. Running them serially wastes wall-clock time — each is
   dominated by external-API and LLM latency.
2. **Real dependencies:** budget needs flight and hotel prices first; the itinerary needs *everything*. These
   cannot run in parallel with the workers.
3. **Human oversight:** a large budget overspend and the final itinerary warrant a human gate before
  proceeding. High-risk safety advisories remain visible but do not pause planning.

A single ReAct agent calling all tools sequentially could not exploit the independence, and a flat tool loop
gave no place to insert human-in-the-loop gates or per-agent isolation.

## Decision

Adopt a **supervisor-routed hybrid** graph in [../../src/agent/stage4_graph.py](../../src/agent/stage4_graph.py):

- A **triage** node classifies shallow vs deep queries; shallow queries short-circuit to a cheap reply.
- A **supervisor** node extracts the user profile and decides routing. It returns a list of
  `Send("<node>", state)` objects — one per requested worker — via `route_after_supervisor`.
- **Six parallel worker nodes** run as *independent graph nodes* (not tool calls). Each worker gets
  per-agent checkpointing, state isolation, and independent failure handling.
- Official safety preflight validates before discovery and emits non-blocking orange/red warnings. Workers
  then **fan in** before the **sequential finishers**
  `budget → budget_review → itinerary → human_review → render_handbook`.

Each worker executes through the `_run_parallel_agent` helper, which **catches exceptions and returns a
graceful-degradation message** instead of crashing the graph — one failing external API cannot take down the
other five workers' results.

## Consequences

**Positive**

- Parallel wall-clock: the six workers overlap instead of summing their latencies.
- Failure isolation: a Duffel/Hotelbeds outage degrades one section, not the whole run.
- Natural insertion points for HITL gates between phases.
- Per-node LangSmith traces are readable and independently debuggable.

**Negative / costs**

- Parallel writes to shared state require **reducers** (see [ADR-0003](0003-custom-reducers-for-parallel-state-merge.md)) — a footgun if forgotten.
- Concurrent LLM calls can burst past Azure TPM quotas — mitigated by semaphores (see [ADR-0004](0004-tiered-models-and-semaphore-concurrency.md)).
- More wiring complexity than a single agent; the graph file is large.

## Alternatives considered

| Alternative | Why rejected | When to choose it instead |
|-------------|--------------|---------------------------|
| **Single ReAct agent** (Stages 1–3) | Serial tool calls; no parallelism; no clean HITL gates | Prototypes, ≤3 tools, no latency pressure |
| **Hierarchical teams-of-agents** | Overkill for 8 agents; extra routing layers add latency and cost | 15+ agents, or agents that must negotiate among themselves |
| **Pure sequential pipeline** | ~6× the wall-clock for the independent workers | When every step genuinely depends on the previous one |

## References

- Code: [../../src/agent/stage4_graph.py](../../src/agent/stage4_graph.py) (`route_after_supervisor`, `_run_parallel_agent`, graph wiring)
- Related: [ADR-0003](0003-custom-reducers-for-parallel-state-merge.md), [ADR-0004](0004-tiered-models-and-semaphore-concurrency.md)
- Overview: [../architecture/ARCHITECTURE_OVERVIEW.md](../architecture/ARCHITECTURE_OVERVIEW.md)
