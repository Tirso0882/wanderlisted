# Budget scope

Read `docs/features/budget/FEATURE.md`, `docs/features/budget/CONTRACTS.md`, `docs/domain/budgeting.md`, and `docs/rules/budget.md`.

Budget arithmetic, normalization, currency conversion, reconciliation, coverage, and verdicts are deterministic. Count only explicitly selected, validated evidence. Deduplicate evidence IDs and rate keys. Treat provider price levels and routes without fares as non-numeric evidence; never invent amounts.

Preserve partial-safe output and source currency when conversion fails. Contingency is opt-in; reserve remains disclosed and excluded from the committed total unless the contract changes. Target changes reuse stored evidence and rates.

Validate with `tests/test_budget_pipeline.py`, budget API/agent tests, and deterministic `tests/test_edd_budget.py`; no live rates or judges by default.
