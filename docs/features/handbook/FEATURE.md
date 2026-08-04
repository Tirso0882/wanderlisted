---
id: feature-handbook
doc_type: feature
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/agent/renderer.py, src/agent/templates/handbook_template.html.j2]
load_when: [handbook, rendering, html, markdown, json]
source_paths: [src/agent/renderer.py, src/agent/templates/handbook_template.html.j2, src/models/itinerary.py]
---

# Handbook

## Outcome

After final plan approval, assemble current typed artifacts into a `TripHandbook` and write equivalent HTML, Markdown, and JSON outputs without additional research or generation.

## Inputs and lifecycle

`render_handbook_node` validates request, skeleton, draft, optional route/budget/readiness, and `ItineraryPlan`; recomputes the artifact fingerprint; then calls `HandbookRenderer`. Assembly maps validated fields, chooses a deterministic destination/season palette, renders Jinja with autoescaping, and writes outputs.

## Rules and failure

Applies `BR-ITI-004`–`006` and `BR-HITL-003`. Missing typed itinerary fails validation. Fingerprint mismatch is `stale`. Filesystem/template/model validation errors are typed failures. Partial plan coverage yields a partial handbook with warnings and unscheduled stops.

## Non-goals

No model, photo provider, place search, price extraction, or prose-to-schema fallback occurs during current rendering.

## Validation

Use renderer and API itinerary contract tests, including zero-call, stale mutation, partial, escaping, and output-format checks. See [`CONTRACTS.md`](CONTRACTS.md) and the shared handbook skill.
