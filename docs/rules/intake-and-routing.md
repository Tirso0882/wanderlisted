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

- **Rule:** Missing capability-specific critical fields return `needs_user_input` before provider/model fan-out.
- **Reason:** Guessed dates, destination, passport, or occupancy create unsafe/costly output.
- **Failure:** End the turn with focused questions.
- **Evidence:** Requirement-policy missing field list.

## BR-INT-003 — Capability routing, not prose ownership

- **Rule:** Supervisor routing uses stable requested capabilities and valid agent names; dependent stages are reached through graph routes.
- **Reason:** A conversational label must not bypass typed prerequisites.
- **Failure:** Invalid routes are filtered or terminate without execution.
- **Evidence:** Routing list plus route-function result.

## BR-INT-004 — Focused work stays focused

- **Rule:** A focused request runs only necessary readiness/prerequisites and requested capability; it does not launch a full itinerary implicitly.
- **Reason:** Limit latency, cost, and unwanted output.
- **Failure:** Extra calls are a routing defect.
- **Evidence:** Requested scope/capabilities and trajectory.
