---
id: rules-itinerary
doc_type: rules
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/itinerary/**, src/models/itinerary.py]
load_when: [itinerary, schedule, feasibility, route]
source_paths: [src/itinerary/pipeline.py, src/itinerary/evidence.py, src/models/itinerary.py]
---

# Itinerary rules

## BR-ITI-001 — Select canonical IDs only

- **Rule:** A selection proposal may reference only catalog place/hotel/flight/rate IDs compatible with canonical city/date/stay constraints.
- **Reason:** Model-created identifiers are not evidence.
- **Failure:** Reject; allow at most the bounded validation retry.
- **Evidence:** Catalog and validated proposal.

## BR-ITI-002 — Deterministic schedule compilation

- **Rule:** Code owns day/date allocation, ordering, time blocks, opening fit, rest insertion, and feasibility.
- **Reason:** Scheduling constraints require reproducible computation.
- **Failure:** Mark infeasible/partial or unscheduled.
- **Evidence:** Draft, opening periods, route legs, compiled blocks.

## BR-ITI-003 — Route measurements stay aligned

- **Rule:** Route legs attach only to their exact ordered stop pair; a missing leg cannot shift a later measurement.
- **Reason:** Misaligned duration/distance corrupts the day plan.
- **Failure:** Mark the leg missing and degrade feasibility.
- **Evidence:** Origin/destination IDs and ordered route plan.

## BR-ITI-004 — Missing facts are not inferred

- **Rule:** Missing hours, route, price, URL, or photo remains missing and creates an explicit limitation where material.
- **Reason:** Plausible defaults become fabricated facts.
- **Failure:** Partial/unscheduled output.
- **Evidence:** Typed optional fields and limitations.

## BR-ITI-005 — Costs are evidence-backed

- **Rule:** Daily/plan cost contains only supported selected/known evidence and agrees with the typed budget boundary.
- **Reason:** Route/places metadata is not fare/admission evidence.
- **Failure:** Exclude unsupported cost.
- **Evidence:** Selected evidence IDs and budget line items.

## BR-ITI-006 — Delivery requires current fingerprint

- **Rule:** Itinerary/handbook delivery requires an artifact fingerprint matching all current canonical inputs and request revision.
- **Reason:** Mixed-version plans are unsafe.
- **Failure:** `stale`; recompile before render.
- **Evidence:** Expected and stored fingerprints.
