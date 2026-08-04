---
id: domain-readiness
doc_type: domain
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/readiness/**, src/agent/agents/travel_readiness_agent.py]
load_when: [readiness, safety, visa, health, weather, culture, packing]
source_paths: [src/readiness, src/agent/agents/travel_readiness_agent.py]
---

# Readiness context

## Purpose

Answer what a traveler must know or prepare before planning proceeds safely.

## Owns

Official advisory preflight, passport-aware entry, official health requirements, exact/seasonal weather, culture/etiquette, practical preparation, and evidence-backed planning constraints.

## Does not own

Attractions/events, restaurants, commercial inventory, transport routes, prices, candidate selection, or final packing presentation.

## Invariants

Sensitive fields require topic/destination-correct official evidence and field citation. Query budgets are bounded. Preflight and detail stages assemble immutably; URL deduplication remaps citations safely. Critical gaps fail closed. Optional failures produce explicit partial/blocked outcomes. Fingerprints prevent stale preflight use.

## Handoff

Downstream contexts receive `TravelReadinessReport` and small actionable `planning_constraints`, not untrusted retrieval transcripts or lists of places.

## Validation

Use readiness pipeline, provider, weather, API-contract, graph-route, and deterministic EDD tests.
