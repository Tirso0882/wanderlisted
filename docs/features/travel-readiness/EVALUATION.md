---
id: evaluation-travel-readiness
doc_type: evaluation
status: active
authority: normative
owners: [travel-platform]
applies_to: [edd/readiness/**, tests/test_readiness_*.py]
load_when: [readiness-evaluation, readiness-edd]
source_paths: [edd/readiness, tests/test_readiness_pipeline.py, tests/test_edd_readiness.py]
---

# Travel readiness evaluation

## Deterministic gates

Required-input no-call behavior, query budgets, ownership exclusions, official topic/destination policy, field citation validity, fingerprint freshness, immutable assembly, fail-closed critical coverage, typed provider errors, and public API shape.

## Semantic dimensions

Groundedness and helpfulness are separate pointwise metrics over pinned evidence. Pairwise experiments compare synthesis variants on identical cases. Judge calibration uses balanced human labels and reports agreement/bias; uncalibrated averages are not release proof.

## Operational exclusions

Provider authentication/quota/network/TLS/timeout failures are `blocked_external` and excluded from model-quality denominators. Live retrieval/model/judge runs require approval and a disclosed call/cost cap. Cached results are valid only for matching fingerprints.
