---
id: domain-context-map
doc_type: domain
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/**, frontend/**]
load_when: [ownership, architecture, cross-layer, refactor]
source_paths: [src/agent/stage4_graph.py, src/models]
---

# Bounded-context map

```text
Request and scope
  -> Orchestration
      -> Readiness -> grounded constraints
      -> Discovery/inventory -> candidate evidence
      -> Itinerary selection -> selected IDs
      -> Routes -> measured legs
      -> Budget -> normalized totals/verdict
      -> Itinerary compiler -> dated plan/fingerprint
      -> Delivery -> handbook/API/frontend

Evaluation observes each boundary without owning runtime truth.
```

| Context | May depend on | Must not own |
|---|---|---|
| Request/scope | User turns, policy requirements | Provider results or final plan |
| Orchestration | Typed contracts/statuses | Provider normalization, arithmetic, domain facts |
| Readiness | Request, official/weather evidence | Places, offers, routes, prices, selections |
| Discovery | Request, readiness constraints | Budget verdict, final schedule, safety approval |
| Budgeting | Selected price evidence, skeleton, request target | Selecting arbitrary offers or inventing prices |
| Itinerary | Canonical evidence, skeleton, route plan, budget, readiness | Provider calls during deterministic compile |
| Delivery | Validated typed artifacts | New research, selection, model-authored facts |
| Evaluation | Runtime inputs/outputs/traces and human labels | Runtime decisions or ground truth generation by tested model |

## Change rule

When a new fact crosses a context, define its typed producer, consumer, evidence/provenance, failure state, and tests before wiring it. Update the appropriate feature contract and `docs/traceability.yaml`.
