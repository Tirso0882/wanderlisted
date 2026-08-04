---
id: domain-delivery
doc_type: domain
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/agent/renderer.py, src/agent/templates/**, src/api/main.py, frontend/**]
load_when: [handbook, renderer, api, frontend, delivery]
source_paths: [src/agent/renderer.py, src/agent/templates/handbook_template.html.j2, src/api/main.py, frontend/src]
---

# Delivery context

## Purpose

Expose typed results through API/streaming/frontend and render the approved trip as HTML, Markdown, and JSON without adding new facts.

## Invariants

Public payloads exclude internal messages and preserve structured statuses/artifacts. HITL resume uses discriminated decision shapes. The handbook builds only from validated current artifacts and rejects fingerprint mismatch as stale. HTML autoescaping remains enabled. All output formats preserve partial coverage, limitations, feasibility, evidence-backed costs, and unscheduled items.

The frontend mirrors backend contracts and does not infer missing values. Session continuity uses the same thread/session ID across chat, stream, state, and resume.

## Validation

Use API contract, renderer, frontend type/lint/build, and focused UI behavior checks. Rendering is provider-free.
