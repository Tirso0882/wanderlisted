# Hotelbeds provider contract

- Implementation: `src/tools/hotels_hotelbeds.py`.
- Tools: `search_hotels_hotelbeds` for availability and `check_hotel_rate_hotelbeds` for CheckRate.
- Authentication: `Api-key` and a fresh SHA-256 `X-Signature` derived from key, secret, and Unix seconds; see `_hotelbeds_headers`.
- Location: destination code, geolocation, or explicit hotel codes. `_resolve_destination_code` owns verified IATA mismatches.
- Occupancy: `_build_occupancies` includes child paxes/ages when supplied.
- Availability: `POST /hotel-api/1.0/hotels`, explicit 20-second timeout.
- CheckRate: `POST /hotel-api/1.0/checkrates`, required for `RECHECK` rate keys.
- Price: provider `net` is emitted as total-stay evidence with its currency; downstream selection still determines whether it is counted.
- Tests: `tests/test_hotels_hotelbeds.py`, `tests/test_hotel_stay_nodes.py`, and budget/itinerary contract tests.

Do not copy specific market coverage, inventory counts, or provider code meanings into prompts unless verified against the current provider specification.
