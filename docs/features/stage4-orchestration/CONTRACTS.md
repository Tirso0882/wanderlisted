---
id: contract-stage4-orchestration
doc_type: contract
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/agent/stage4_graph.py, src/agent/state.py, src/api/main.py, frontend/**]
load_when: [graph-contract, state, api, stream, resume]
source_paths: [src/agent/state.py, src/models/component_result.py, src/api/main.py]
---

# Stage 4 contracts

## State write contract

- Nodes return partial state updates, not mutated shared state.
- Parallel component writes use distinct keys under reducer-backed dictionaries.
- Typed artifacts use stable `*_structured` keys; machine outcomes use `component_results[component]`.
- `ComponentStatus` values are `queued`, `running`, `completed`, `partial`, `needs_user_input`, `no_inventory`, `blocked_external`, `failed`, and `stale`.

## Routing contract

Every node has an explicit inbound path, outbound route/edge, failure/terminal behavior, and test. Dependent routing checks structured status, current workflow state, and fingerprints. Generic destination planning does not imply flight, hotel, entry-readiness, or budget execution. Pre-interrupt provider work is checkpointed.

## Public API contract

`POST /api/v1/chat` and `/chat/stream` share a validated public session ID. A signed HttpOnly browser-principal cookie owns that ID, and every checkpoint/history/resume lookup uses a derived opaque internal thread ID. Traced chat responses and SSE `done` events return the actual enclosing LangSmith run ID; when tracing is disabled they return `null`, never a fabricated identifier. `/chat/resume` accepts discriminated safety, budget, or human-review decisions, with a bounded legacy approval shape. Internal identities, messages, and provider payloads are not public components. `/health` is liveness; `/ready` confirms graph initialization and reports only non-secret checkpoint/rate-limit backend names.

## Frontend contract

TypeScript discriminated decisions and structured artifact types mirror the backend. Streaming labels are presentation signals; final `done`/resume payload is authoritative for components and interruption state.

## Change checklist

When adding a node or public artifact, update state/reducer, dependency construction, graph registration/routes, component status/fingerprint, API sanitation/stream labels, frontend types/store/views, tests, feature docs, and traceability.
