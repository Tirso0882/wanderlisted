# 0004 — Three-tier model pyramid + per-tier semaphore gating

**Status:** Accepted · **Date:** 2026-07-10 (retroactively documented) · **Deciders:** Tirso Gomez

## Context

The parallel fan-out ([ADR-0001](0001-multi-agent-supervisor-parallel-fanout.md)) can fire many concurrent
LLM calls in a single super-step. Two forces collide:

1. **Cost & fit:** not every task needs the most capable model. Routing, extraction, and rendering are cheap
   classification tasks; deep multi-source synthesis is not. Using one large model everywhere is wasteful;
   using one small model everywhere is underpowered.
2. **Quota ceilings:** each Azure OpenAI deployment has a **tokens-per-minute (TPM)** cap. A concurrent burst
   of parallel agents can exceed it and trigger `429` rate-limit errors.

## Decision

**a) Three-tier model pyramid** — assign a tier by *task complexity*, not by agent name, in
[../../src/agent/stage4_graph.py](../../src/agent/stage4_graph.py) (`_AGENT_TIERS`) and
[../../src/agent/llm.py](../../src/agent/llm.py):

| Tier | Model | Used by |
|------|-------|---------|
| `reasoning` | gpt-5.4 | Destination (7 tools, RAG+web synthesis), Itinerary (cross-destination day plans) |
| `fast` | gpt-5.4-mini | Flights, Hotels, Restaurants, Activities, Transportation, Budget (one API + format) |
| `utility` | gpt-5.4-nano | Triage, Supervisor, render, shallow replies (classify / extract / format) |

Each tier **falls back** to the next higher tier when its env vars are absent, so the system runs unchanged on
a single-deployment setup.

**b) Per-tier semaphore gating** — [../../src/agent/concurrency.py](../../src/agent/concurrency.py) wraps every
model in a `_SemaphoreLLM` proxy that gates `ainvoke()` (and `astream`, and structured-output chains via
`_SemaphoreRunnable`) through a shared `asyncio.Semaphore`. Caps are derived from TPM budgets:

```
reasoning = 4    # ~300K TPM / ~15K per run
fast      = 15   # ~500K TPM / ~6K per run
utility   = 15   # ~200K TPM / ~2K per run
```

The proxy forwards all other attributes transparently, so `bind_tools`, `with_structured_output`, and
LangChain internals keep working unmodified.

## Consequences

**Positive**

- **Cost optimization is architectural**, not an afterthought — cheap tasks run on the cheapest model.
- **429 protection** without an external rate limiter — bursts queue on the semaphore instead of failing.
- Transparent proxy means agents don't know they're gated; no call-site changes.
- One dial (`_SEMAPHORE_LIMITS`) to retune per deployment.

**Negative / costs**

- Caps are **hand-tuned** against quota, not auto-discovered — monitor semaphore wait time in LangSmith and
  adjust. Too low → queueing/latency; too high → 429s.
- Tier misassignment is possible (e.g. giving a tool-heavy agent the utility tier) — mitigated by the
  "classify by task complexity" rule and the reasoning constraints in [ADR-0002](0002-responses-api-for-reasoning-models.md).
- `invoke` (sync) is intentionally left ungated because the graph is fully async.

## Alternatives considered

| Alternative | Why rejected | When to choose it instead |
|-------------|--------------|---------------------------|
| **One model for everything** | Either too costly (big model) or too weak (small model) | Very small systems, or when only one deployment exists |
| **External rate limiter (gateway/proxy)** | More infra to run; in-process semaphore is simpler and quota-aware | Multi-service fleets sharing one quota pool |
| **Retry-only on 429** | Wastes tokens, adds latency, thundering-herd under load | As a *secondary* safety net on top of gating |

## References

- Code: [../../src/agent/concurrency.py](../../src/agent/concurrency.py) (`_SemaphoreLLM`, `_SEMAPHORE_LIMITS`)
- Code: [../../src/agent/llm.py](../../src/agent/llm.py) (tier factory, fallback), [../../src/agent/stage4_graph.py](../../src/agent/stage4_graph.py) (`_AGENT_TIERS`)
- Related: [ADR-0001](0001-multi-agent-supervisor-parallel-fanout.md), [ADR-0002](0002-responses-api-for-reasoning-models.md)
