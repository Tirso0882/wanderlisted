---
id: evaluation-itinerary
doc_type: evaluation
status: active
authority: normative
owners: [travel-platform]
applies_to: [edd/itinerary/**, tests/test_itinerary_*.py]
load_when: [itinerary-evaluation, itinerary-edd]
source_paths: [edd/itinerary, tests/test_itinerary_pipeline.py, tests/test_edd_itinerary.py]
---

# Itinerary evaluation

## Deterministic gates

Catalog identity, selection compatibility/duplicates, bounded retry/fail-closed behavior, route-leg alignment, opening-fit behavior, missing-evidence degradation, rest rules, supported costs, contiguous dates, artifact fingerprint changes, stale rendering, and zero provider/model calls in compiler/render.

## Semantic dimensions

Judge only traveler usefulness/coherence grounded in the fixed typed plan; keep it separate from deterministic correctness. Pairwise comparisons receive identical evidence and run both orders. Calibrate against human labels before using a judge threshold.

## Operational exclusions

Live Maps/model/judge failures are not itinerary-quality failures. Default Layer 1 and focused tests are offline; any live capture requires approval and disclosed case/call/cost limits.
