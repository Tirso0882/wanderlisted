---
name: langgraph-stage4
description: Change or diagnose the Wanderlisted production LangGraph, node wiring, Send fan-out, reducer fan-in, routing, component gates, checkpointing, HITL interrupt/resume, dependent planning stages, or lost parallel state.
---

# Stage 4 LangGraph

## Inputs

Identify the affected capability, state fields, predecessor/successor nodes, routing condition, retry/checkpoint behavior, API/frontend consumers, and required tests. Read `../../../docs/features/stage4-orchestration/FEATURE.md`, `../../../docs/features/stage4-orchestration/CONTRACTS.md`, and [the graph checklist](references/graph-checklist.md).

## Workflow

1. Inspect `TravelAgentState`, the relevant node and route functions, graph registration, agent registry, typed models, and focused tests.
2. Draw the smallest before/after path. Include early termination, error/partial status, interrupts, resume, and stale state.
3. Assign one owner for each new fact or decision. Keep provider normalization in tools, orchestration in the graph, and deterministic domain decisions in their package.
4. For parallel work, emit one `Send` per independent unit, write unique mergeable keys, and verify the reducer. Never rely on last-writer behavior for shared dictionaries.
5. Use `ComponentResult` for machine outcomes and keep conversational messages separate. Gates must inspect structured status, not prose.
6. Put critical preconditions before paid/dependent work. Preserve readiness preflight checkpointing so resume does not repeat provider calls.
7. Wire every new node completely: dependency construction, `add_node`, inbound route, outbound route, terminal/error behavior, streaming/API labels, and tests.
8. Validate routing functions directly, then node behavior, then a hermetic graph path. Inspect API/frontend contracts when state is public.

## Stop conditions

Stop if a change needs a new cross-context business decision without a documented rule, if reducer semantics are ambiguous, or if validation would invoke live models/providers without approved budget.

## Output

Report the changed path, state contract, ownership, failure/interrupt behavior, tests, and any public contract impact.

## Validation

```bash
.venv/bin/pytest tests/test_nodes.py tests/test_component_gate.py -q
.venv/bin/pytest tests/test_integration.py -q -m "not integration"
.venv/bin/ruff check src/agent tests/test_nodes.py
```
