---
id: domain-budgeting
doc_type: domain
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/budget/**, src/models/budget.py, src/models/pricing.py]
load_when: [budget, pricing, currency, target]
source_paths: [src/budget, src/models/budget.py, src/models/pricing.py]
---

# Budgeting context

## Purpose

Produce an auditable total and target comparison from selected evidence, known costs, deterministic estimates, and explicit currency quotes.

## Invariants

Only validated selected flight/hotel evidence enters committed inventory totals. Evidence IDs/rate keys are deduplicated. Scope/basis determines multiplication; conversion is decimal, cached per pair, and recorded. Regional estimates are disclosed. Non-numeric signals remain non-numeric. Arithmetic, rounding, reconciliation, coverage, and verdict are deterministic.

Contingency is user opt-in. Reserve is disclosed separately and excluded from the committed total under the current contract. Conversion failure preserves source values and prevents an unsupported verdict.

## Handoff

The review gate consumes reliable material overage and typed target information. Itinerary/handbook consume `BudgetBreakdown`, not re-parsed budget prose.

## Validation

Use budget pipeline, model/API, node, and deterministic EDD tests.
