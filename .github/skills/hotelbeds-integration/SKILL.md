---
name: hotelbeds-integration
description: 'Integrate and debug the Hotelbeds hotel API in Wanderlisted. WHEN working on hotel search or booking, search_hotels_hotelbeds, check_hotel_rate_hotelbeds, hotels_hotelbeds.py, no hotels returned, empty hotel results, signature or 401/403 auth error, X-Signature, RECHECK rate, rateKey, checkrates, board codes (RO/BB/HB/FB/AI), star rating / category code, cancellation policy, occupancies / paxes / children, destination code, or adding hotel filters.'
---

# Hotelbeds Booking API

Implementation: [src/tools/hotels_hotelbeds.py](../../../src/tools/hotels_hotelbeds.py).
Two `@tool` functions: `search_hotels_hotelbeds` (availability) and
`check_hotel_rate_hotelbeds` (rate verification).

## Durable invariants

- **Auth is a signed header, not a token.** Every request needs
  `Api-key`, `X-Signature = SHA256(apiKey + secret + unixSeconds)`,
  `Accept: application/json`, and `Accept-Encoding: gzip`. Signature is
  time-based, so a clock skew or a stale signature causes 401/403. See
  `_hotelbeds_headers()`.
- **`RECHECK` rates are not bookable as-is.** When an availability rate has
  `rateType == "RECHECK"`, you MUST call `check_hotel_rate_hotelbeds`
  (`POST /checkrates`) with its `rateKey` to get a final price before it can be
  trusted or booked. `BOOKABLE` rates are final. This branch is handled in
  `_format_hotel()` and surfaced via `recheck_hotels`.
- **Net prices are final** — they already include supplements and discounts. Do
  not add markup math on top.
- **Board and category codes are opaque** — `RO/BB/HB/FB/AI` for board,
  `{N}EST` for star rating. Resolve to human text via `_parse_star_rating()` and
  the board helpers, not by guessing.

## Two-step vs three-step booking

- BOOKABLE rate: Availability → Booking.
- RECHECK rate: Availability → **CheckRate** → Booking.

## Common failure modes

- **Empty results** — usually destination resolution: check
  `_resolve_destination_code()` maps the IATA/city correctly, and that
  occupancies are built via `_build_occupancies()` (children need `paxes` with
  ages).
- **401/403** — signature/clock issue, or missing `Api-key`/secret env vars.
- **Booking rejected after search** — the rate was `RECHECK` and was never
  re-verified via `/checkrates`.

## Source of truth / verify against

- Signed headers: `_hotelbeds_headers()` in [src/tools/hotels_hotelbeds.py](../../../src/tools/hotels_hotelbeds.py)
- Availability call: `_search_hotelbeds_api()`; rate check: `_check_rate_api()`
- RECHECK handling: `_format_hotel()` (rate loop) + `recheck_hotels` in `search_hotels_hotelbeds`
