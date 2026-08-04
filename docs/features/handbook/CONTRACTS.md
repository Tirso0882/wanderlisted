---
id: contract-handbook
doc_type: contract
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/agent/renderer.py, src/agent/templates/**, outputs/**]
load_when: [handbook-contract, renderer-contract]
source_paths: [src/agent/renderer.py, src/models/itinerary.py, tests/test_itinerary_renderer.py]
---

# Handbook contracts

## Source contract

Only validated structured artifacts populate handbook fields. `TripHandbook` is the single content model for HTML/Markdown/JSON. A missing optional field remains empty/limited; the renderer never mines conversational messages for facts.

## Presentation contract

Jinja autoescaping stays enabled. CSS/vanilla tab behavior remains self-contained in the template. Palette choice is table/fallback driven. Output paths are returned in `handbook_paths`; generated files remain ignored artifacts.

## Consistency contract

The same destinations, dates, selected flights/accommodation, day plan, budget, readiness, and limitations appear across formats. Public API can expose `handbook_structured` but not internal source messages.
