---
name: handbook-rendering
description: 'Modify the Wanderlisted trip handbook HTML/Markdown/JSON output. WHEN editing renderer.py or handbook_template.html.j2, changing itinerary HTML, adding or reordering a tab, theme colors / season palette look wrong, HandbookRenderer, TripHandbook model, HANDBOOK_ASSEMBLY_PROMPT extraction, render_handbook_node, styling/CSS of the handbook, Google Maps embed, or blank/missing sections in the rendered handbook.'
---

# Trip Handbook Rendering

Output generation is a **3-layer pipeline** — know which layer your change
belongs to before editing.

1. **Extract**: `HANDBOOK_ASSEMBLY_PROMPT` (per-section LLM extraction, batched
   with retry) → `TripHandbook` Pydantic model.
2. **Render**: `HandbookRenderer` fills the single Jinja2 template
   [src/agent/templates/handbook_template.html.j2](../../../src/agent/templates/handbook_template.html.j2).
3. **Write**: `write_outputs()` emits HTML / Markdown / JSON.

## Durable invariants

- **One template, 8 tabs** (Itinerary, Flights, Hotels, Budget, Maps, Safety,
  Culture, Packing). **All CSS is inlined**; JS is vanilla and only switches
  tabs. Do not add build tooling, external stylesheets, or JS frameworks.
- **Theme color is destination + season specific**, selected via `_pick_accent()`
  against the `_SEASON_PALETTES` map keyed by `(destination_slug, season)`. To
  add a look, add palette entries — do not hardcode colors in the template.
- **A blank tab is almost always an extraction gap, not a template bug** — the
  `TripHandbook` field came back empty from layer 1. Debug the prompt/model
  before touching Jinja.

## Where to make which change

| Change | Layer | File |
|---|---|---|
| Wording/fields captured | Extract | `HANDBOOK_ASSEMBLY_PROMPT` in `agent_prompt.py` |
| New data field | Extract + Model | prompt + `TripHandbook` in `src/models/itinerary.py` |
| Layout / new tab / styling | Render | `handbook_template.html.j2` |
| Theme colors | Render | `_SEASON_PALETTES` / `_pick_accent()` in `renderer.py` |
| Output file formats | Write | `write_outputs()` |

## Source of truth / verify against

- Renderer + palettes: `HandbookRenderer`, `SeasonPalette`, `_SEASON_PALETTES` in [src/agent/renderer.py](../../../src/agent/renderer.py)
- Template: [src/agent/templates/handbook_template.html.j2](../../../src/agent/templates/handbook_template.html.j2)
- Model: `TripHandbook` in [src/models/itinerary.py](../../../src/models/itinerary.py)
- Graph node: `render_handbook_node` in [src/agent/stage4_graph.py](../../../src/agent/stage4_graph.py)
