---
id: rules-budget
doc_type: rules
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/budget/**, src/models/budget.py]
load_when: [budget, target, currency, contingency]
source_paths: [src/budget/pipeline.py, src/budget/currency.py, src/models/budget.py]
---

# Budget rules

## BR-BUD-001 — Deterministic arithmetic

- **Rule:** Decimal normalization, multiplication, conversion, rounding, category totals, and reconciliation are code-owned.
- **Reason:** Model arithmetic is non-auditable.
- **Failure:** Validation failure; never repair totals with prose.
- **Evidence:** Line items, rate records, category sums, total.

## BR-BUD-002 — One conversion quote per pair

- **Rule:** A run fetches/caches one validated rate per distinct currency pair and records it.
- **Reason:** Mixed rates make totals irreproducible.
- **Failure:** Preserve source amount and mark conversion unavailable.
- **Evidence:** `ConversionRateRecord` and status.

## BR-BUD-003 — Partial-safe coverage

- **Rule:** Missing/failed categories remain visible; an unsupported conversion or missing selected critical price prevents a reliable target verdict.
- **Reason:** A precise-looking incomplete total is misleading.
- **Failure:** Partial coverage and unknown/blocked verdict.
- **Evidence:** Coverage, limitations, conversion statuses.

## BR-BUD-004 — Disclosed deterministic estimates

- **Rule:** Non-inventory estimates use documented regional baselines and trip scope; unresolved location uses an explicit global fallback.
- **Reason:** Estimates must be explainable and repeatable.
- **Failure:** Mark estimate source/limitation; do not call it live price.
- **Evidence:** Estimate source, region, basis, scope.

## BR-BUD-005 — Contingency is opt-in

- **Rule:** Apply contingency only when supplied; disclose reserve separately and exclude it from committed total under the current contract.
- **Reason:** Silent buffers distort target comparison.
- **Failure:** No contingency line is added.
- **Evidence:** Request percentage and reserve field.

## BR-BUD-006 — Material target review uses reliable totals

- **Rule:** Budget HITL triggers only from a reliable material overage under configured policy; target adjustments reuse validated evidence/rates.
- **Reason:** Review must not interrupt on incomplete or newly invented totals.
- **Failure:** Skip gate or return to deterministic recomputation.
- **Evidence:** Target, verdict, difference, review decision.
