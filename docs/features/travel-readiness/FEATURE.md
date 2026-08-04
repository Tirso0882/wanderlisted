---
id: feature-travel-readiness
doc_type: feature
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/readiness/**, src/agent/agents/travel_readiness_agent.py]
load_when: [travel-readiness, readiness, safety, entry, health, weather]
source_paths: [src/readiness, src/agent/agents/travel_readiness_agent.py, tests/test_readiness_pipeline.py]
---

# Travel readiness

## Outcome

Produce a cited `TravelReadinessReport` describing safety/preparation facts and actionable constraints for the current traveler, or stop safely when critical evidence/inputs are unavailable.

## Inputs

Canonical destinations, dates, passport country when entry is requested, requested readiness topics, locale, and bounded provider configuration. Place interests are not readiness research instructions.

## Pipeline

Planning creates bounded topic/destination queries. Preflight retrieves/synthesizes official safety evidence and fingerprints it. Details retrieve requested official-sensitive/culture/practical evidence plus exact Open-Meteo weather when supported. Grounding removes unsupported fields/items, coverage classifies each topic, and immutable assembly preserves stage-owned fields while remapping deduplicated citations.

## Outputs

The report contains destinations, advisory/entry/health/weather/culture/practical/packing content, sources, citations, limitations, and `planning_constraints`. The graph wraps it in a typed `ComponentResult` with coverage-derived status and fingerprint.

## Rules and failure

Applies `BR-RDY-001`–`005`. Missing destination/passport returns input-required without search. Critical advisory/evidence/provider failure blocks downstream discovery. Optional gaps remain partial and visible. Stale preflight is rejected.

## Non-goals

No attractions, events, restaurants, inventory, routes, monetary estimates, or final itinerary selection.

## Validation

Use pipeline/provider/weather/grounding/API/graph tests plus the deterministic readiness EDD layer. See [`CONTRACTS.md`](CONTRACTS.md) and [`EVALUATION.md`](EVALUATION.md).
