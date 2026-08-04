---
id: feature-budget
doc_type: feature
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/budget/**, src/models/budget.py, src/agent/agents/budget_agent.py]
load_when: [budget, pricing, currency, target]
source_paths: [src/budget/pipeline.py, src/budget/evidence.py, src/models/budget.py]
---

# Budget

## Outcome

Create an auditable `BudgetBreakdown` in the target currency from selected inventory, known costs, disclosed deterministic estimates, and validated exchange-rate records.

## Inputs and lifecycle

The graph supplies `TripRequest`, `TripSkeleton`, normalized component evidence, and any prior validated budget/rates for target adjustment. `BudgetAgent` performs bounded typed extraction only where legacy inputs require it; `BudgetPipeline` owns evidence validation, conversion, line items, coverage, totals, reconciliation, and target verdict.

## Outputs

Source/converted line items, category amounts, total, target/difference/verdict, coverage/limitations, conversion records/status, non-numeric evidence, contingency reserve, and evidence IDs.

## Rules and failure

Applies `BR-SEL-001`–`005` and `BR-BUD-001`–`006`. Unsupported/duplicate/unselected prices are excluded. Conversion failure preserves source value and blocks unsupported verdict. Partial coverage is explicit. Target adjustment recomputes deterministically from stored evidence.

## Non-goals

The feature does not select flight/hotel candidates, infer provider prices from text, or transform routes/price levels into money.

## Validation

Use pipeline, agent legacy-boundary, API review, node, model, and deterministic EDD tests. See [`CONTRACTS.md`](CONTRACTS.md) and [`EVALUATION.md`](EVALUATION.md).
