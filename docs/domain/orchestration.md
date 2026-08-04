---
id: domain-orchestration
doc_type: domain
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/agent/stage4_graph.py, src/agent/state.py]
load_when: [graph, orchestration, routing, hitl, state]
source_paths: [src/agent/stage4_graph.py, src/agent/state.py]
---

# Orchestration context

## Purpose

Sequence independent and dependent capabilities, merge state safely, checkpoint human decisions, and prevent invalid artifacts from advancing.

## Invariants

- Triage and intake happen before general planning unless a developer target uses the validated direct route.
- Readiness/preflight precedes discovery when required.
- Parallel workers write reducer-safe unique component keys and fan into a structured gate.
- Hotels depend on exact city stays; routes depend on validated draft selections; budget and itinerary depend on typed evidence.
- Safety, budget, and human review decisions are typed and checkpointed. Resume must not repeat pre-interrupt provider work.
- Routes inspect statuses/fingerprints, never prose.

## Failure behavior

Invalid, missing-input, no-inventory, external-blocked, rejected, and stale paths terminate or return to their documented owner. Synthesis may answer focused follow-ups from existing data without re-running tools.

## Validation

Test node outputs, every changed route branch, reducer merging, interrupts/resume, API streaming labels, and terminal behavior.
