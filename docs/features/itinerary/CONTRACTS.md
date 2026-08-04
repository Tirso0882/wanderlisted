---
id: contract-itinerary
doc_type: contract
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/models/itinerary.py, src/itinerary/**, src/api/main.py, frontend/**]
load_when: [itinerary-contract, itinerary-api, itinerary-frontend]
source_paths: [src/models/itinerary.py, src/itinerary/pipeline.py, src/api/main.py]
---

# Itinerary contracts

## Catalog and selection

Catalog evidence owns canonical IDs and immutable provider facts. A proposal carries only selected IDs grouped by canonical date/city/stay. Resolver validates compatibility and creates a `DraftItinerary`; selected hotel rate keys cannot be duplicated across stays.

## Route contract

Each `RouteLeg` binds exact origin/destination IDs and retains duration/distance/mode/source. A missing leg remains missing. Route order may influence schedule order but cannot overwrite place facts.

## Plan contract

Days are contiguous from start to end. Time blocks reference canonical places/accommodation and contain only supported costs. `coverage_status`, `feasibility_status`, missing constraints, and unscheduled stops match compiled evidence. Fingerprint covers request revision and all canonical source artifacts.

## Public/delivery contract

API and frontend preserve typed itinerary/handbook structures. Renderer recomputes expected fingerprint and returns `stale` on mismatch. Human edit returns to draft selection; approval alone permits rendering.
