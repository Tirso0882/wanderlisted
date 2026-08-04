---
id: adr-0007
doc_type: adr
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/readiness/**, src/agent/stage4_graph.py]
load_when: [readiness, safety, orchestration]
source_paths: [src/readiness, src/agent/stage4_graph.py, tests/test_readiness_pipeline.py]
supersedes: [adr-0006]
---

# ADR-0007: Travel readiness ownership and fail-closed preflight

**ADR status:** Accepted — 2026-08-03

## Context

The earlier destination pipeline mixed planning readiness with place discovery and retained legacy naming. Current planning needs a bounded safety/readiness owner whose evidence can gate downstream discovery without selecting attractions or prices.

## Decision

`src/readiness` and `TravelReadinessAgent` are the only current readiness boundary. They own advisory preflight, entry, health, weather, culture, practical preparation, and grounded planning constraints. Activities owns named places/events; inventory specialists own offers; downstream deterministic stages own selection, pricing, and itinerary assembly.

Official critical evidence is required before safety-sensitive discovery. The preflight is fingerprinted and checkpointed before HITL so resume neither accepts stale inputs nor repeats the provider call. Missing critical evidence fails closed with a typed outcome.

## Consequences

- Downstream agents receive small grounded constraints rather than a destination research transcript.
- Sensitive coverage and provider failures remain observable.
- New place-discovery behavior cannot be added to readiness.
- Historical `DestinationAgent` names and compatibility aliases are not current contracts.

## Alternatives considered

- Keep a broad destination agent: rejected because ownership and evidence policy remain ambiguous.
- Let each discovery worker research safety independently: rejected because it duplicates calls and cannot enforce one preflight gate.

## Supersession

This ADR supersedes the ownership and compatibility portions of ADR-0006. ADR-0006 remains historical evidence for the decision to replace destination RAG with bounded live retrieval.

## Evidence

Implementation is in `src/readiness/` and readiness routes in `src/agent/stage4_graph.py`; focused evidence is in readiness pipeline, provider, API-contract, and EDD tests.
