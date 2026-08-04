---
id: testing-strategy
doc_type: testing
status: active
authority: normative
owners: [travel-platform]
applies_to: [tests/**, src/**, frontend/**]
load_when: [testing, validation, regression]
source_paths: [tests, pyproject.toml, frontend/package.json]
---

# Testing strategy

## Principles

Test behavior at its owning boundary, then add contract tests where typed data crosses graph/API/frontend/renderer layers. Default validation is deterministic, offline, and credential-free. A passing unit test proves its fixture contract, not live-provider quality.

## Layers

| Layer | Purpose | Examples |
|---|---|---|
| Model/domain | Validation, arithmetic, fingerprints, compilation | budget/itinerary/readiness pipeline tests |
| Tool | Request construction, normalization, failure classification | mocked Duffel/Hotelbeds/Google/Tavily tests |
| Node/route | State writes, reducer behavior, gates, termination | node/component-gate tests |
| Contract | Public API and cross-layer typed compatibility | budget/readiness/itinerary API tests |
| Integration (hermetic) | Multi-component flow with fakes | integration tests excluding live marker |
| Frontend | Types, state, rendering, build | ESLint/Next build and focused UI tests |
| EDD | Agent outcomes, trajectories, judges, calibration | `edd/` plus `test_edd_*` |
| Live/deploy | Provider/platform readiness | approval-gated smoke only |

## Required cases

Cover success, empty/no inventory, invalid input, partial evidence, external blocked, duplicate/mismatch, stale artifact, interrupt/resume, and the reported regression as applicable. Assert typed statuses/fields and exact owner behavior rather than only output strings.

## Commands

Use repository executables and narrowest scope:

```bash
.venv/bin/pytest tests/<focused>.py -q
.venv/bin/ruff check <touched-python-paths>
.venv/bin/ruff format --check <touched-python-paths>
cd frontend && pnpm lint && pnpm build
make docs-check
```

Never enable integration/live paths or real credentials implicitly.
