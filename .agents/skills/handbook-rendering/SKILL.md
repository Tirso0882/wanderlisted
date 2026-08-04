---
name: handbook-rendering
description: Modify or diagnose Wanderlisted handbook assembly, HTML, Markdown, JSON, Jinja layout, tabs, palette, missing sections, artifact fingerprints, renderer failures, or the render_handbook graph node.
---

# Handbook rendering

## Inputs

Identify whether the change concerns typed source data, deterministic assembly, template layout, output writing, or graph delivery. Read `../../../docs/features/handbook/FEATURE.md`, `../../../src/agent/AGENTS.md`, and [the rendering map](references/rendering-map.md).

## Workflow

1. Inspect `TripHandbook`, `ItineraryPlan`, the renderer, graph node, and focused tests before editing.
2. Reproduce with typed fixtures. Determine whether data is absent before `build_handbook`, rejected as stale/invalid, or lost in the template.
3. Change the owning layer only: typed model for schema, deterministic assembler for mapping, Jinja for presentation, palette tables for theme, or `write_outputs` for formats.
4. Preserve the artifact-fingerprint check. Source mutation after itinerary compilation must return `stale`, not render mixed data.
5. Keep assembly provider-free. The current render path must make zero model, photo, or other network calls.
6. Preserve partial coverage, limitations, feasibility warnings, evidence-backed costs, and unscheduled stops in every output format.
7. Verify HTML escaping, tabs/navigation, Markdown content, JSON validation, and output paths with temporary directories.

## Stop conditions

Stop if the requested presentation requires facts absent from typed artifacts; fix the upstream contract instead of parsing prose or inventing content. Stop before opening rendered output via a live service or adding a provider call without explicit authorization.

## Output

Report the owning layer changed, artifact fields affected, output formats verified, and whether stale/partial behavior remains intact.

## Validation

```bash
.venv/bin/pytest tests/test_itinerary_renderer.py -q
.venv/bin/ruff check src/agent/renderer.py tests/test_itinerary_renderer.py
```
