# Rendering map

- Typed artifact: `src/models/itinerary.py` (`TripHandbook`, `ItineraryPlan`).
- Deterministic assembly and formats: `src/agent/renderer.py` (`HandbookRenderer.build_handbook`, `render_html`, `render_markdown`, `write_outputs`).
- HTML/Jinja/CSS/JS: `src/agent/templates/handbook_template.html.j2`.
- Graph validation/delivery: `render_handbook_node` in `src/agent/stage4_graph.py`.
- Fingerprint producer: `compute_artifact_fingerprint` in `src/itinerary/pipeline.py`.
- Contract tests: `tests/test_itinerary_renderer.py` and `tests/test_api_itinerary_contract.py`.

Static handbook extraction prompts still exist in the prompt module for compatibility/history, but the current `render_handbook_node` builds from validated structured artifacts and does not invoke them.
