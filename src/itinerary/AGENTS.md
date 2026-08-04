# Itinerary scope

Read `docs/features/itinerary/FEATURE.md`, `docs/features/itinerary/CONTRACTS.md`, `docs/domain/itinerary.md`, and `docs/rules/itinerary.md`.

Selection may choose only canonical place, hotel, flight, and rate IDs in the evidence catalog. The deterministic compiler owns dates, ordering, timing, route-leg attachment, feasibility, supported daily costs, and artifact fingerprints. Do not let model prose create facts.

Fail closed after the bounded selection retry. Missing hours/routes degrade explicitly; they do not justify invented times or measurements. Changes to typed plans must be traced through graph state, API exposure, frontend types, renderer, and stale-artifact checks.

Run the focused itinerary pipeline, API-contract, renderer, node, and deterministic EDD tests. Do not call Maps, models, or image providers by default.
