---
id: feature-stage4-orchestration
doc_type: feature
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/agent/stage4_graph.py, src/agent/state.py, src/api/main.py]
load_when: [stage4, graph, orchestration, routing, hitl]
source_paths: [src/agent/stage4_graph.py, src/agent/state.py, src/api/main.py]
---

# Stage 4 orchestration

## Outcome

Route a typed request through only the necessary capability owners, run independent work concurrently, enforce prerequisite/gate order, pause/resume human decisions safely, and deliver structured outcomes without losing partial/error evidence.

## Lifecycle

Triage chooses shallow reply or planning. Intake accumulates a valid `TripRequest`. Supervisor routes focused/full capabilities. Safety preflight and acknowledgement precede discovery when needed; readiness details precede workers that consume constraints. Flights/restaurants/activities can fan out; their structured results fan into a component gate. Exact skeleton drives per-stay hotel fan-out. Draft selection, routes, budget, reviews, itinerary compilation, final review, and handbook are dependent stages.

## State model

`messages` is conversation presentation. `component_results` records machine status/error/evidence/fingerprint. `itinerary_components` stores typed artifacts and normalized component payloads. Parallel dictionaries use merge reducers; scalar workflow fields use explicit last-value behavior.

## Rules

Applies `BR-INT-001`–`004`, `BR-RDY-003`/`005`, and `BR-HITL-001`–`005`. Routes must never infer success from message prose.

## Failure behavior

Clarification, no inventory, blocked external, failed, rejected, and stale outcomes terminate or return to the documented owner. Component gates prevent downstream drafting from error text. Resume uses the same thread/checkpoint and typed decision.

## Non-goals

The graph does not normalize provider payloads, perform budget arithmetic, create itinerary facts, or own business truth that belongs to domain packages.

## Validation

Focused evidence: `tests/test_nodes.py`, `tests/test_component_gate.py`, API contract/resume tests, and hermetic graph integration tests. See [`CONTRACTS.md`](CONTRACTS.md).
