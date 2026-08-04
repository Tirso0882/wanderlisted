---
id: domain-discovery
doc_type: domain
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/agent/agents/**, src/tools/**]
load_when: [flights, hotels, activities, restaurants, transportation, discovery, inventory]
source_paths: [src/agent/agents, src/tools]
---

# Discovery and inventory context

## Purpose

Translate a scoped request and grounded constraints into provider-backed candidate flights, hotel rates, places, restaurants, and routes.

## Invariants

- Tools own authentication, requests, timeouts, retries, normalization, and redaction.
- Specialists may format candidates but cannot manufacture unavailable facts.
- Candidates retain stable provider/place IDs, dates/stays, source URL, currency/price scope, and limitations.
- Hotel search executes per exact city stay after the trip skeleton. `RECHECK` is not final selection truth until verified.
- Transportation routes only canonical draft selections and preserves stop/leg alignment.

## Failure behavior

No inventory, authentication, timeout, rate limit, provider, validation, and internal failure remain distinguishable. The component gate blocks dependent planning when required inputs are unusable; optional gaps may proceed only under documented partial behavior.

## Validation

Mock provider HTTP in unit tests and verify normalized markers/evidence. Live calls are approval-gated integration evidence.
