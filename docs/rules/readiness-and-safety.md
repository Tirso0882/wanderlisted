---
id: rules-readiness-safety
doc_type: rules
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/readiness/**, src/agent/stage4_graph.py]
load_when: [readiness, safety, entry, health, weather]
source_paths: [src/readiness, src/agent/stage4_graph.py]
---

# Readiness and safety rules

## BR-RDY-001 — Official evidence for critical topics

- **Rule:** Safety advisories and requested sensitive entry/health facts require destination/topic-correct configured official evidence and field citations.
- **Reason:** Search summaries or unrelated official domains are not authoritative proof.
- **Failure:** Critical coverage is blocked/failed closed.
- **Evidence:** Source authority/topic tags and cited field IDs.

## BR-RDY-002 — Passport-aware entry research

- **Rule:** Personalized entry requirements require `passport_country`; destination alone is insufficient.
- **Reason:** Entry rules depend on nationality/document.
- **Failure:** `needs_user_input` without external search.
- **Evidence:** Canonical request and query plan.

## BR-RDY-003 — Current preflight only

- **Rule:** Safety review/details may consume preflight only when its fingerprint matches current destinations, passport, dates, and topics.
- **Reason:** A changed request invalidates prior safety evidence.
- **Failure:** Reject as stale and rerun only through the approved route.
- **Evidence:** Request/preflight fingerprints.

## BR-RDY-004 — Readiness does not discover places

- **Rule:** Readiness queries and outputs exclude attractions, venues, events, restaurants, and commercial inventory.
- **Reason:** Activities/inventory contexts own those facts and selections.
- **Failure:** Remove the query/output and treat as ownership defect.
- **Evidence:** Query plan and `planning_constraints`.

## BR-RDY-005 — Bounded partial behavior

- **Rule:** Query budgets/retries are bounded; optional provider gaps are explicit partial limitations, while critical advisory failure blocks discovery.
- **Reason:** Reliability requires predictable cost and safe degradation.
- **Failure:** Typed `partial` or `blocked_external`, never fabricated completion.
- **Evidence:** Coverage state, limitations, failures, tools called.
