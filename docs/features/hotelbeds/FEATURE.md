---
id: feature-hotelbeds
doc_type: feature
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/tools/hotels_hotelbeds.py, src/agent/agents/hotels_agent.py]
load_when: [hotelbeds, hotels, accommodation, checkrate]
source_paths: [src/tools/hotels_hotelbeds.py, src/agent/agents/hotels_agent.py]
---

# Hotelbeds integration

## Outcome

Search Hotelbeds availability for each exact city stay and retain stable hotel/rate evidence that downstream selection and budget can validate; verify `RECHECK` rates before treating them as current.

## Inputs and lifecycle

Trip skeleton supplies city/stay dates and request occupancy. The graph fans one hotel worker per stay, the tool resolves a supported destination code/location, builds occupancies and filters, signs the request, normalizes returned hotels/rates, then fan-in aggregates all stays. Hotel gate checks structured outcomes before itinerary draft selection.

## Outputs

Human-readable candidate content plus a machine marker with hotel/rate identity, net/currency, rate type, stay scope, board/cancellation/tax/provider metadata, URLs when present, and recheck list.

## Rules and failure

Applies `BR-SEL-001`–`004`. Fresh signed headers are required. Requests have bounded timeout/retry. Empty inventory differs from authentication/provider/timeout failure. `RECHECK` availability is not final selected price until CheckRate.

## Non-goals

No booking/purchase workflow is authorized by this feature. Availability order does not select accommodation and net price does not bypass downstream validation.

## Validation

Use mocked Hotelbeds tool tests, hotel-stay/fan-in graph tests, and downstream budget/itinerary selected-rate tests. Live test-environment calls require approval. See [`CONTRACTS.md`](CONTRACTS.md).
