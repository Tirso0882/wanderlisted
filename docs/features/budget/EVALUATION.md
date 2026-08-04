---
id: evaluation-budget
doc_type: evaluation
status: active
authority: normative
owners: [travel-platform]
applies_to: [edd/budget/**, tests/test_budget*.py]
load_when: [budget-evaluation, budget-edd]
source_paths: [edd/budget, tests/test_budget_pipeline.py, tests/test_edd_budget.py]
---

# Budget evaluation

## Deterministic release gates

Money validation, scope multiplication, selected-only counting, ID/amount/currency agreement, deduplication, one-rate-per-pair caching, conversion failure, rounding/reconciliation, target adjustment reuse, contingency separation, regional/global estimate disclosure, and non-numeric evidence handling.

## Semantic evaluation

Use judges only for explanation clarity/helpfulness against the already-computed breakdown. A judge never decides arithmetic correctness. Pairwise comparisons use identical structured input in both position orders and require calibration before release thresholds.

## Cost controls

Layer-1 fixtures are default. Any live currency/provider/model/judge path requires explicit approval and case/call/cost disclosure. External failures are operational exclusions, not budget-quality scores.
