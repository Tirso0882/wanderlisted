---
id: contract-hotelbeds
doc_type: contract
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/tools/hotels_hotelbeds.py, src/budget/evidence.py, src/itinerary/evidence.py]
load_when: [hotelbeds-contract, hotel-price, hotel-selection]
source_paths: [src/tools/hotels_hotelbeds.py, src/budget/evidence.py, src/itinerary/evidence.py]
---

# Hotelbeds contracts

## Request

Exactly one location mode is used: Hotelbeds destination code, geolocation, or explicit hotel codes. Stay dates and occupancy are required; children include ages when known. Filters and result limits are bounded.

## Authentication and transport

Every request builds `Api-key` plus a fresh SHA-256 `X-Signature` from key, secret, and current Unix seconds. Secrets/signed request material are never logged. Availability and CheckRate use explicit timeouts and bounded transport retries.

## Rate evidence

`rateKey`, hotel identity, stay, provider net/currency, rate type, board, cancellation, and selection status stay linked. `RECHECK` must be revalidated through CheckRate; downstream counts only exact selected evidence. Provider `net` is represented as a total-stay candidate, not automatically committed truth.

## Failure

Input validation, no inventory, authentication, timeout/network, provider HTTP, and internal parsing remain distinguishable for graph/component status and evaluation exclusions.
