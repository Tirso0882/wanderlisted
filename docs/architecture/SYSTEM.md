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

FastAPI exposes chat, streaming, history, account/session, webhook, health, feedback, and HITL endpoints. A signed HttpOnly browser principal owns each public session ID; the API derives an opaque owner-scoped checkpoint thread ID before calling LangGraph. Optional Clerk identity adds an opaque account owner after server-side JWT validation without replacing guest ownership. A compiled graph with a checkpointer owns session execution, while PostgreSQL indexes session metadata only. `TravelAgentState` keeps messages separate from machine-readable `component_results` and `itinerary_components`.

The Next.js server is the browser-to-API trust boundary: it removes browser-supplied authorization and, when Clerk is fully configured, forwards only a server-obtained Clerk token. The feature-gated Atlas Sunrise workspace localizes interface copy in English or Polish while preserving historical messages, provider facts, routes, prices, typed statuses, limitations, and evidence unchanged.

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
- `ui_locale` is a presentation fallback. Clear message language selects the response locale; ambiguous turns retain the last clear conversation language. Intake changes `TripRequest.locale` only on clear language evidence.
- The session registry stores opaque owner keys, immutable checkpoint thread IDs, deterministic titles, timestamps, locale, and message count. Checkpoints remain authoritative for messages, interrupts, and artifacts.

## Reliability and trust boundaries

Providers and model outputs are untrusted inputs. Tools normalize provider payloads; domain pipelines validate identifiers and evidence; deterministic stages own arithmetic and schedule construction; critical readiness fails closed; HITL is checkpointed. Logs and API payloads must not expose credentials or internal transcripts.

## Current operational limits

The API uses PostgreSQL checkpoints whenever `CHECKPOINT_BACKEND=postgres`; production rejects process-local memory checkpoints. The saver is opened for the FastAPI lifespan, initializes its schema idempotently, and closes during shutdown. Local Compose exercises the PostgreSQL path. Azure receives the database URL as a secure deployment parameter, but the managed database, backups, retention, and recovery remain environment prerequisites rather than resources owned by this repository.

Deployed environments require the stable session-signing secret, PostgreSQL session registry, and Redis-backed rate limiting. Redis decisions are atomic across workers/replicas and fail closed on backend errors, so the API may scale horizontally. Direct development may use bounded in-process implementations. Anonymous browser ownership remains the base identity; cross-device history exists only after explicit session claiming into an enabled Clerk account. The internal single-replica Redis container is still an availability dependency and should be replaced or given an explicit recovery owner before a high-availability claim.

Atlas Sunrise is the single frontend experience in every environment. Clerk application setup, keys, passwordless email and Google connections, allowed origins, webhook delivery, consultation URLs, and production enablement are external rollout prerequisites. `CLERK_ENABLED` defaults off in deployed parameter files.

## Change protocol

Any cross-context contract change updates the owning feature pack, business rules, `traceability.yaml`, focused tests, public API/frontend types, and an ADR when it changes an accepted architectural decision.
