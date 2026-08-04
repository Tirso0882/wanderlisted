---
id: feature-itinerary
doc_type: feature
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/itinerary/**, src/models/itinerary.py, src/agent/agents/itinerary_agent.py]
load_when: [itinerary, schedule, selection, feasibility]
source_paths: [src/itinerary/pipeline.py, src/itinerary/evidence.py, src/models/itinerary.py]
---

# Itinerary

## Outcome

Turn provider-backed candidates and canonical planning artifacts into a contiguous, feasible `ItineraryPlan` whose facts, routes, costs, limitations, and fingerprint are auditable.

## Inputs and lifecycle

Evidence catalog construction normalizes places/hotels/flights from component results and the exact `TripSkeleton`. One bounded structured model call proposes catalog IDs; deterministic validation rejects unknown, duplicate, wrong-city/date/stay, or reused-rate selections and allows one corrective retry. Transportation routes the validated draft. The compiler combines draft, route, readiness, budget, and request revision into dated time blocks and a fingerprint.

## Outputs

Validated `DraftItinerary`, optional `RoutePlan`, and final plan with days/time blocks, selected accommodation, transit steps, weather/context, supported daily cost, feasibility, unscheduled stops, missing constraints, coverage, and artifact fingerprint.

## Rules and failure

Applies `BR-SEL-001`–`005` and `BR-ITI-001`–`006`. Missing hours/routes degrade explicitly. Closed or impossible stops move to unscheduled/infeasible; measurements never shift between stops. Selection fails closed after one retry. Non-contiguous or stale plans are invalid.

## Non-goals

The compiler makes no model/provider/photo calls and does not invent opening hours, route measurements, prices, URLs, or place facts.

## Validation

Use pipeline, node, API-contract, renderer, model, and deterministic EDD tests. See [`CONTRACTS.md`](CONTRACTS.md) and [`EVALUATION.md`](EVALUATION.md).
