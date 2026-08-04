---
id: contract-travel-readiness
doc_type: contract
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/readiness/**, src/agent/stage4_graph.py, src/api/main.py]
load_when: [readiness-contract, readiness-api, readiness-grounding]
source_paths: [src/readiness/models.py, src/readiness/assembly.py, src/readiness/coverage.py]
---

# Travel readiness contracts

## Evidence contract

Each source has a canonical ID/URL, topic/destination scope, authority status, and retrieval provenance. Field/item citation IDs must resolve after URL deduplication. Sensitive fields without qualifying evidence are cleared, not hedged into prose.

## Fingerprint contract

The request fingerprint covers normalized destinations, passport, date window, and selected topics. Preflight/details/safety routes compare it before reuse.

## Stage ownership

Preflight owns advisory-critical content. Details owns the remaining requested topics. Assembly rejects destination mismatch, source-ID collision, orphan citations/constraints, and cross-stage overwrites.

## Handoff contract

Public API exposes the structured report and status without internal messages. Discovery consumes only actionable grounded constraints. It must not interpret source snippets independently or treat readiness output as place discovery.
