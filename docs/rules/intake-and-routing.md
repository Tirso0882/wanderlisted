---
id: rules-intake-routing
doc_type: rules
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/agent/nodes/intake.py, src/agent/agents/supervisor_agent.py, src/agent/stage4_graph.py]
load_when: [intake, routing, scope, supervisor]
source_paths: [src/agent/nodes/intake.py, src/agent/policies/requirements.py, src/agent/stage4_graph.py]
---

# Intake and routing rules

## BR-INT-001 — Canonical request merge

- **Rule:** Each turn updates `TripRequest` only with explicit/safely inferred patch fields and preserves prior confirmed values.
- **Reason:** Follow-ups must not erase travel constraints.
- **Failure:** Validation error or clarification; never silent replacement.
- **Evidence:** Typed patch and request revision.

## BR-INT-002 — Required inputs before dependent work

- **Rule:** Missing capability-specific critical fields, service-scope confirmation, or exact route scope return `needs_user_input` before provider/model fan-out.
- **Rule:** A traveler may explicitly delegate endpoint and overnight-city selection for an existing broad route goal. Intake records the delegation and may produce only a bounded ordered city proposal from canonical trip constraints; it must not invent availability, times, distances, prices, or provider facts. Concrete proposed cities are still required before fan-out.
- **Rule:** Accepting hotel search for a party with children requires one age per child before Hotelbeds execution.
- **Rule:** A generic city-break or itinerary request defaults to destination planning (restaurants, activities, local transportation, and itinerary). Flight, hotel, entry-readiness, and budget fields become blocking only when that optional capability was explicitly requested.
- **Reason:** Guessed dates, destination, passport, or occupancy create unsafe/costly output.
- **Failure:** End the turn with focused questions.
- **Evidence:** Requirement-policy missing field list.

## BR-INT-003 — Capability routing, not prose ownership

- **Rule:** Supervisor routing uses the canonical authorized capabilities and valid agent names; dependent stages are reached through graph routes. UI tabs and keyword-based presentation hints never select execution agents.
- **Reason:** A conversational label must not bypass typed prerequisites.
- **Failure:** Invalid routes are filtered or terminate without execution.
- **Evidence:** Routing list plus route-function result.

## BR-INT-004 — Named services are not implicitly exclusive

- **Rule:** When a traveler names some services, intake offers the remaining applicable services before external work. A typed fingerprinted decision may include all, include selected additions, or confirm the current services only.
- **Rule:** Explicit exclusivity such as “only flights and hotels,” “that is all,” or an equivalent localized statement confirms the named scope without another offer. Confirmed focused work runs only its selected capabilities and prerequisites.
- **Rule:** Generic planning language is not implicit consent for bookable inventory, personalized entry research, or budget calculation.
- **Reason:** Limit latency, cost, and unwanted output.
- **Failure:** Calls before confirmation, omitted named services, or extra declined services are routing defects.
- **Evidence:** Requested/declined capabilities, offer fingerprint/decision, authorized routing, and trajectory.
