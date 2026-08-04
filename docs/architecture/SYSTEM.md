---
id: architecture-system
doc_type: architecture
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/**, frontend/**]
load_when: [architecture, graph, api, cross-layer]
source_paths: [src/agent/stage4_graph.py, src/agent/state.py, src/api/main.py]
---

# System architecture

## Purpose

Wanderlisted turns a conversational travel request into evidence-backed structured planning artifacts and, after required human decisions, a deterministic handbook. The design separates probabilistic classification/selection from deterministic validation, arithmetic, compilation, and rendering.

## Runtime boundary

FastAPI exposes chat, SSE streaming, session/history, health/readiness, feedback, and HITL resume endpoints. A compiled LangGraph with a checkpointer owns session execution. `TravelAgentState` keeps conversation messages separate from machine-readable `component_results` and `itinerary_components`.

## Primary lifecycle

```text
request
  -> triage -> structured intake -> supervisor
  -> readiness preflight/HITL when required
  -> readiness details -> discovery fan-out -> component gate
  -> exact trip skeleton -> per-stay hotels -> hotel gate
  -> bounded draft selection -> transportation routes
  -> deterministic budget -> budget review
  -> deterministic itinerary -> human review
  -> deterministic handbook -> API/frontend
```

Focused requests may terminate after one capability or synthesis. Every route can also end with `needs_user_input`, `no_inventory`, `blocked_external`, `failed`, or `stale` rather than advancing invalid prose.

## Ownership

| Context | Owns |
|---|---|
| Request/scope | Canonical `TripRequest`, merge semantics, required inputs |
| Readiness | Official-sensitive preparation evidence and planning constraints |
| Discovery/inventory | Provider calls and normalized offers/places |
| Orchestration | Routing, fan-out/fan-in, gates, checkpoint/HITL lifecycle |
| Budget | Selected evidence, conversion, arithmetic, coverage, verdict |
| Itinerary | Canonical selection validation and deterministic plan compilation |
| Delivery | Typed handbook assembly and HTML/Markdown/JSON rendering |
| Evaluation | Datasets, evaluators, baselines, judges, calibration |

See [`CONTEXT_MAP.md`](../domain/CONTEXT_MAP.md) for permitted handoffs.

## Core contracts

- `TripRequest` is the language-independent request accumulated across turns.
- `ComponentResult` is the machine outcome; messages are presentation only.
- `TravelReadinessReport`, `TripSkeleton`, pricing evidence, `DraftItinerary`, `RoutePlan`, `BudgetBreakdown`, `ItineraryPlan`, and `TripHandbook` are typed artifacts.
- Parallel dictionary writes require declared reducers. Independent workers write unique keys.
- Evidence identifiers and request/artifact fingerprints prevent cross-run or stale-data mixing.
- Static runtime prompts live only in `src/agent/prompts/agent_prompt.py`.

## Reliability and trust boundaries

Providers and model outputs are untrusted inputs. Tools normalize provider payloads; domain pipelines validate identifiers and evidence; deterministic stages own arithmetic and schedule construction; critical readiness fails closed; HITL is checkpointed. Logs and API payloads must not expose credentials or internal transcripts.

## Current operational limits

The API process contains in-memory rate limiting, while graph persistence depends on the configured checkpointer. Docker Compose includes Redis/Postgres, but the current application/infra must be verified before assuming those services provide durable production state. Horizontal scaling is unsafe until persistence and rate limiting are explicitly shared and tested.

## Change protocol

Any cross-context contract change updates the owning feature pack, business rules, `traceability.yaml`, focused tests, public API/frontend types, and an ADR when it changes an accepted architectural decision.
