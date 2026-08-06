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

Catalog evidence owns canonical IDs and immutable provider facts. Activities/restaurants must expose typed place evidence to be completed; transcript-marker parsing is compatibility-only. A proposal carries only selected IDs grouped by canonical date/city/stay. Resolver validates compatibility and creates a `DraftItinerary`; selected hotel rate keys cannot be duplicated across stays. When hotel search is authorized, every stay requires one validated rate. When it is not authorized, accommodation remains empty and deterministic city-centre anchors support routing without asserting lodging facts or prices. A minimum beach-day constraint requires at least that many distinct canonical days with selected provider evidence typed as a beach; search wording or prose does not satisfy it.

## Route contract

Each `RouteLeg` binds exact origin/destination IDs and retains duration/distance/mode/source. A missing leg remains missing. Route order may influence schedule order but cannot overwrite place facts.

## Plan contract

Days are contiguous from start to end. Time blocks reference canonical places/accommodation and contain only supported costs. `coverage_status`, `feasibility_status`, missing constraints, and unscheduled stops match compiled evidence. Fingerprint covers request revision and all canonical source artifacts.

## Public/delivery contract

API and frontend preserve typed itinerary/handbook structures. Renderer recomputes expected fingerprint and returns `stale` on mismatch. Human edit returns to draft selection; approval alone permits rendering.
