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
- Exact/flexible dates, traveler occupancy, passport/origin, destinations, requested capabilities, budget, preferences, and constraints remain typed.
- Capability IDs are stable domain names, not graph node/class names.
- Incomplete requirements end the turn as `needs_user_input`; the system does not guess critical dates, destination, passport, or occupancy.

## Outputs and collaborators

The supervisor consumes the request and requirement policy. Discovery receives only relevant profile/request fields. Readiness fingerprints destinations, dates, passport, and topics. Budget and itinerary consume the same canonical request revision.

## Validation

Use trip-request, intake, requirement-policy, and routing tests.
