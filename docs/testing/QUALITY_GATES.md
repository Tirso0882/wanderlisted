---
id: testing-quality-gates
doc_type: testing
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/**, frontend/**, docs/**, infra/**]
load_when: [quality-gate, release, review, definition-of-done]
source_paths: [.github/workflows/ci.yml, Makefile, tests]
---

# Quality gates

## Change gate

- Focused tests for every changed behavior and failure branch pass.
- Ruff check/format-check passes for touched Python.
- Typed public contracts and consumers remain aligned.
- `make docs-check` passes when documentation/rules/routes change.
- No unrelated/pre-existing diff changes.

## Pull-request gate

CI secret scan, lint/format, unit suite/coverage policy, deterministic Layer-1 evaluation, documentation contract, and PR Docker build pass. No job may invoke provider/model/Azure/Tavily/paid judge paths.

## Release gate

All PR gates plus approved image provenance, environment configuration, migrations/persistence review, health/readiness probes, rollback reference, observability, and security/cost checks. Any live smoke is separately approved with target/call/cost limits.

## AI-quality gate

Critical deterministic policy has zero failures. Semantic thresholds require a versioned dataset, anchored rubric, human calibration, and documented denominator/exclusions. `blocked_external`/infra errors block reliability claims but do not count as model-quality failures.

## Documentation gate

Metadata/status/authority valid; links/paths exist; IDs unique; active business rules trace to implementation and evidence; ADR supersession valid; indexes current; instruction/skill/context budgets hold; Copilot adapter remains thin.
