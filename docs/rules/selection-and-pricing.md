---
id: rules-selection-pricing
doc_type: rules
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/models/pricing.py, src/budget/**, src/itinerary/**, src/tools/**]
load_when: [selection, pricing, offers, hotel-rate, evidence]
source_paths: [src/models/pricing.py, src/budget/evidence.py, src/itinerary/evidence.py]
---

# Selection and pricing rules

## BR-SEL-001 — Availability is not selection

- **Rule:** Candidate inventory enters committed truth only after explicit validated selection.
- **Reason:** Search order or presence does not express user/system choice.
- **Failure:** Candidate remains unselected and excluded from committed totals/plans.
- **Evidence:** Stable selected offer/rate/place ID.

## BR-SEL-002 — Identifier and amount must agree

- **Rule:** Legacy or structured selected price is accepted only when provider ID, amount, currency, stay/scope, and source evidence agree.
- **Reason:** Nearby numbers and prose are unsafe price extraction.
- **Failure:** Reject the numeric claim.
- **Evidence:** Canonical evidence record.

## BR-SEL-003 — Deduplicate evidence identity

- **Rule:** The same selected evidence ID or hotel rate key is counted once per valid scope.
- **Reason:** Parallel/legacy representations must not double count.
- **Failure:** Duplicate is ignored or selection rejected when ambiguous.
- **Evidence:** Normalized identity/scope key.

## BR-SEL-004 — Preserve price semantics

- **Rule:** Currency, amount, price scope, basis, source, timestamp, and selection status survive every handoff.
- **Reason:** Correct multiplication/conversion depends on semantics, not labels.
- **Failure:** Evidence is incomplete/non-committable.
- **Evidence:** Typed `Money`/price evidence.

## BR-SEL-005 — Non-numeric signals stay non-numeric

- **Rule:** Price levels, rankings, duration/distance, or routes without fares cannot become monetary amounts.
- **Reason:** Such conversion fabricates cost.
- **Failure:** Record as non-numeric evidence/limitation.
- **Evidence:** Typed non-numeric record.
