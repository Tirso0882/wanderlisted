---
id: domain-itinerary
doc_type: domain
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/itinerary/**, src/models/itinerary.py]
load_when: [itinerary, schedule, selection, route, feasibility]
source_paths: [src/itinerary, src/models/itinerary.py]
---

# Itinerary context

## Purpose

Select canonical candidates and compile them into a dated, feasible, evidence-preserving plan.

## Invariants

A bounded model call may propose only IDs found in the evidence catalog; deterministic validation owns identity, city/date/stay compatibility, duplicates, and the one-retry fail-closed boundary. Routes may order stops and attach measured legs but cannot replace place facts.

The compiler owns times, opening-fit checks, rest rules, feasibility, supported daily costs, unscheduled stops, coverage, and artifact fingerprint. Missing hours/routes degrade explicitly. Dates are contiguous and align to the skeleton.

## Handoff

Human review receives `ItineraryPlan`. Delivery verifies its fingerprint against current request, skeleton, draft, route, budget, and readiness artifacts before rendering.

## Validation

Use itinerary pipeline, renderer, API-contract, node, and deterministic EDD tests.
