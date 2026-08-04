---
id: architecture-data-integrations
doc_type: architecture
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/tools/**, src/readiness/**, src/budget/**]
load_when: [provider, integration, evidence, pricing, data]
source_paths: [src/tools, src/readiness/retrieval.py, src/budget/currency.py]
---

# Data and integrations

## Integration boundaries

| Capability | Current boundary | Required retained evidence |
|---|---|---|
| Flights | Duffel offers/places | offer/segment IDs, exact amount/currency, dates, source scope |
| Hotels | Hotelbeds availability and CheckRate | hotel/rate keys, stay, net/currency, rate type, board/cancellation |
| Places and routes | Google Places/Maps/Routes | place IDs, URLs/photos/hours, ordered route legs and measurements |
| Readiness research | Tavily plus official-source policy | normalized URL, topic/destination ownership, authority status, citations |
| Exact weather | Open-Meteo | dated values, provider URL, coverage/limitation |
| Currency | ExchangeRate-API | pair, decimal rate, provider timestamp; cached per pair |
| Models | provider selected by `LLM_PROVIDER` | typed output or content blocks, tier, failure classification |

Provider names describe current adapters, not permanent domain contracts. Domain code consumes normalized typed evidence and stable IDs.

## Data rules

- Credentials come from environment/secret references and never enter documents, prompts, traces, errors, or persisted caches.
- Every network call has a bounded timeout; retries are limited to safe transient failures.
- Preserve source currency and scope. Conversion creates a cited rate record; it never mutates the original evidence.
- Availability is not selection. Only validated selected evidence can enter committed budget/itinerary truth.
- Non-numeric provider signals remain non-numeric. Price levels, rankings, or route duration cannot be converted into invented amounts.
- Sensitive readiness facts require configured official authority and field-level citation. A search-generated summary is not evidence.
- Normalize/deduplicate URLs and IDs without merging different destinations, dates, stays, or topics.

## Failure classification

Authentication, rate limit, timeout, provider rejection, validation, and internal failures remain distinct. Critical missing readiness evidence blocks downstream work; optional provider gaps may produce partial results. External failures are excluded from model-quality denominators.

## Adding or changing an adapter

Update the tool contract, normalized marker/schema, feature pack, selection/pricing rules, traceability, mocked tests, and every downstream consumer of the evidence. A live smoke test is optional and approval-gated; mocked contract evidence is mandatory.
