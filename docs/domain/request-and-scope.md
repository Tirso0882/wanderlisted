---
id: domain-request-scope
doc_type: domain
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/models/trip_request.py, src/agent/nodes/intake.py]
load_when: [intake, request, scope, routing]
source_paths: [src/models/trip_request.py, src/agent/nodes/intake.py, src/agent/policies/requirements.py]
---

# Request and scope context

## Purpose

Accumulate user intent across turns into one language-independent `TripRequest`, determine focused/full/refinement scope, and expose missing required inputs before expensive work.

## Invariants

- Merge only fields explicitly supplied or safely inferred in the current turn; do not erase prior confirmed values with absent patch fields.
- Exact/flexible dates, traveler occupancy/child ages, passport/origin, confirmed or explicitly delegated city destinations, broad route goals/waypoints, transport mode, requested/declined capabilities, budget, preferences, and constraints such as minimum beach days remain typed.
- Capability IDs are stable domain names, not graph node/class names.
- Generic city-break and itinerary requests use the destination-planning bundle. Flights, hotels, travel readiness, and budget are opt-in capabilities with their own input requirements.
- Naming some services is not an exclusive request. Before provider/model fan-out, intake offers remaining applicable services unless the traveler explicitly confirms that the named services are the complete scope.
- Broad regions, borders, corridors, coastlines, and seas are route goals, not overnight cities. Exact route endpoints and overnight cities are traveler-confirmed or produced as a bounded proposal after the traveler explicitly delegates the choice; the typed resolution is required before discovery and skeleton allocation.
- Incomplete requirements end the turn as `needs_user_input`; the system does not guess critical dates, destination, route cities, passport, occupancy, transport mode, or service consent.

## Outputs and collaborators

The supervisor consumes the request and requirement policy. Discovery receives only relevant profile/request fields. Readiness fingerprints destinations, dates, passport, and topics. Budget and itinerary consume the same canonical request revision.

## Validation

Use trip-request, intake, requirement-policy, and routing tests.
