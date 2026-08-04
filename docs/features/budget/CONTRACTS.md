---
id: contract-budget
doc_type: contract
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/models/pricing.py, src/models/budget.py, src/budget/**, src/api/main.py]
load_when: [budget-contract, pricing-contract, budget-api]
source_paths: [src/models/pricing.py, src/models/budget.py, src/budget/pipeline.py]
---

# Budget contracts

## Price evidence

`Money` is non-negative decimal amount plus normalized currency. Price evidence retains category, source/evidence ID, scope, basis, selection status, and provider metadata. Known costs are explicit user/domain facts. Non-numeric price evidence is never passed to arithmetic.

## Breakdown invariants

Category amounts reconcile exactly to total under declared rounding. Each converted amount references one recorded pair/rate. Coverage and verdict agree with conversion/evidence completeness. Reserve is separate from total.

## Review/API

Material overage can interrupt at `budget_review` under configured HITL policy. Typed decisions are proceed, cancel, or adjust target. The API continues reading supported legacy payloads but emits the typed current budget contract.

## Downstream

Itinerary and handbook consume the structured breakdown. They may present line items/limitations but may not recompute or extract totals from prose.
