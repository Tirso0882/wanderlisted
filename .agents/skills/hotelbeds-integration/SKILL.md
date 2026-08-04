---
name: hotelbeds-integration
description: Integrate, modify, or debug Hotelbeds availability and CheckRate behavior, signed authentication, destination codes, occupancy, rate keys, RECHECK rates, boards, cancellation policies, prices, empty inventory, or Hotelbeds HTTP failures.
---

# Hotelbeds integration

## Inputs

Collect the environment (test/production), request dates/city/occupancy, provider response classification, and whether the task is availability or rate verification. Read `../../../docs/features/hotelbeds/FEATURE.md`, `../../../src/tools/AGENTS.md`, and [the provider contract](references/provider-contract.md).

## Workflow

1. Inspect `src/tools/hotels_hotelbeds.py` and its tests. Confirm current endpoint, payload, limits, and normalized marker format from code.
2. Validate inputs before HTTP: dates, exactly one location mode, rooms/adults/children and child ages, filters, and destination-code resolution.
3. Build fresh signed headers for each request. Keep API key/secret and signed request material out of logs/errors.
4. Use bounded timeouts/retries. Retry request transport failures only as implemented; preserve provider HTTP errors as classified failures.
5. Preserve stable hotel/rate keys, currency, net total, stay scope, board, cancellation, tax, and rate type in normalized evidence.
6. Treat `RECHECK` as unconfirmed until `check_hotel_rate_hotelbeds` returns the verified rate. Do not use an availability amount as selected truth after a required recheck.
7. Trace contract changes through hotel fan-out/fan-in, pricing evidence, itinerary selection, budget, tests, and documentation.

## Stop conditions

Stop before a live request unless the user approved the environment, expected request count, and possible cost/quota impact. Stop if credentials would need to be displayed or production booking/mutation is requested without explicit authority.

## Output

Return the failure boundary or implemented contract change, normalized evidence impact, mocked test results, and any skipped live verification.

## Validation

```bash
.venv/bin/pytest tests/test_hotels_hotelbeds.py tests/test_hotel_stay_nodes.py -q
.venv/bin/ruff check src/tools/hotels_hotelbeds.py tests/test_hotels_hotelbeds.py
```
