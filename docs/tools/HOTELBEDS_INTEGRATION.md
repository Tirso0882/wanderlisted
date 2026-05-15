# Hotelbeds (HBX Group) — Integration Guide

> Deep-dive technical documentation for the Hotelbeds hotel search integration in Wanderlisted.

**Status:** Production-ready (test environment)
**Source files:** `src/tools/hotels_hotelbeds.py`, `src/agent/agents/hotels_agent.py`
**Tests:** `tests/test_hotels_hotelbeds.py` (36 tests)
**OpenAPI spec:** `docs/tools/APIs/hotelbeds/OpenAPI-Hotel-BookingAPI-3.0.yaml`

---

## Table of Contents

- [Overview](#overview)
- [API Suite](#api-suite)
- [Authentication](#authentication)
- [Implemented Endpoints](#implemented-endpoints)
  - [Availability Search](#1-availability-search)
  - [CheckRate](#2-checkrate)
- [Data Model](#data-model)
- [How It Fits in the Agent Architecture](#how-it-fits-in-the-agent-architecture)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Board Codes Reference](#board-codes-reference)
- [Error Handling](#error-handling)
- [Troubleshooting](#troubleshooting)
- [API Endpoints Not Yet Implemented](#api-endpoints-not-yet-implemented)
- [External Documentation](#external-documentation)

---

## Overview

Hotelbeds (HBX Group) provides access to **250K+ hotel properties** worldwide, with strength in independent, boutique, and locally-owned hotels not found on Amadeus. It complements our Amadeus integration to give travellers the widest possible hotel coverage.

**Why two hotel sources?**

| Source | Strengths | Inventory |
| ------ | --------- | --------- |
| Amadeus | Major chains, loyalty programs, GDS-connected | 150K+ hotels |
| Hotelbeds | Independents, boutiques, local properties | 250K+ hotels |

The `HotelsAgent` calls **both** sources in parallel and merges results, deduplicating by hotel name and preferring the lower price.

---

## API Suite

Hotelbeds offers three complementary APIs:

| API | Purpose | Our Usage |
| --- | ------- | --------- |
| **Booking API** | Real-time availability, rates, bookings | ✅ Core integration |
| **Content API** | Static hotel data (descriptions, photos, facilities, room types) | 🔲 Future enhancement |
| **Cache API** | Hourly CSV snapshots for bulk pricing | 🔲 Not planned (for price-comparison sites) |

---

## Authentication

All Hotelbeds API calls require two headers:

```
Api-key: <your_api_key>
X-Signature: SHA256( apiKey + secret + unixTimestampInSeconds )
```

The signature is **time-sensitive** — it uses the current Unix timestamp in seconds. Our implementation in `_hotelbeds_headers()` recomputes it on every call.

**Required environment variables:**

| Variable | Description |
| -------- | ----------- |
| `HOTELBEDS_API_KEY` | API key from [Hotelbeds Developer Portal](https://developer.hotelbeds.com) |
| `HOTELBEDS_API_SECRET` | API secret from the same portal |
| `HOTELBEDS_BASE_URL` | Optional. Defaults to `https://api.test.hotelbeds.com`. Set to `https://api.hotelbeds.com` for production. |

**Additional headers sent:**

```
Accept: application/json
Accept-Encoding: gzip
Content-Type: application/json
```

---

## Implemented Endpoints

### 1. Availability Search

**Endpoint:** `POST /hotel-api/1.0/hotels`
**Timeout:** 5s (API-side), 20s (client-side)
**Tool:** `search_hotels_hotelbeds`

Searches for available hotels in a destination with full filtering support.

#### Parameters

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `city_code` | str | required | IATA city code (e.g., `TYO`, `PAR`) |
| `check_in_date` | str | required | YYYY-MM-DD format |
| `check_out_date` | str | required | YYYY-MM-DD format |
| `adults` | int | 2 | Number of adults |
| `children` | int | 0 | Number of children |
| `children_ages` | str | `""` | Comma-separated ages (e.g., `"4,8"`) |
| `min_category` | int | None | Minimum star rating 1-5 |
| `max_rate` | float | None | Maximum total price |
| `board_codes` | str | `""` | Comma-separated board codes (e.g., `"BB,HB"`) |

#### What the response includes

For each hotel (up to 8 returned):
- Hotel name, star category, zone/destination, coordinates (lat/lng)
- Up to 2 rooms per hotel, each with:
  - Room name, total price, board type, rate type
  - **Daily rate breakdown** (per-night pricing)
  - **Cancellation policies** (penalty amounts and dates)
  - **Promotions** (e.g., "Early Booking", "Non-Refundable Rate")
  - **Tax summary** (included vs excluded)
  - **Rate key** (needed for CheckRate or booking)
- RECHECK warning when rates require verification

#### Internal API request body

```json
{
  "stay": { "checkIn": "2026-06-15", "checkOut": "2026-06-20" },
  "occupancies": [{
    "rooms": 1,
    "adults": 2,
    "children": 2,
    "paxes": [{ "type": "CH", "age": 4 }, { "type": "CH", "age": 8 }]
  }],
  "destination": { "code": "TYO" },
  "filter": {
    "maxHotels": 50,
    "maxRooms": 5,
    "minCategory": 3,
    "maxRate": 500.0
  },
  "boards": { "board": ["BB", "HB"], "included": true },
  "dailyRate": true
}
```

---

### 2. CheckRate

**Endpoint:** `POST /hotel-api/1.0/checkrates`
**Timeout:** 15s (API-side), 30s (client-side)
**Tool:** `check_hotel_rate_hotelbeds`

Verifies the current price and returns detailed rate breakdown. **Mandatory** for rates where `rateType == "RECHECK"`.

#### Parameters

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `rate_keys` | str | required | One or more rate keys separated by `\|\|\|` |
| `include_upselling` | bool | False | Return higher-category room options |

#### What the response includes

- Confirmed total price (may differ from availability)
- Modification policies (can cancel? can modify?)
- **Rate breakdown:** discounts (e.g., Early Booking: -25.00) and supplements (e.g., Single Supplement: +30.00)
- **Cancellation policies** with exact dates and penalty amounts
- **Rate comments** (check-in/check-out times, special conditions)
- **Upselling options** — higher-category rooms with their rate keys

#### When to use CheckRate

```
Availability response
       │
       ├── rateType: "BOOKABLE" ──→ Can proceed directly to booking
       │
       └── rateType: "RECHECK" ──→ MUST call CheckRate first
                                     (price may have changed)
```

---

## Data Model

The Hotelbeds response maps to Wanderlisted's `HotelOption` model:

| Hotelbeds Field | HotelOption Field | Notes |
| --------------- | ----------------- | ----- |
| `name` | `name` | Direct mapping |
| `categoryCode` ("3EST") | `star_rating` (3) | Parsed from `{N}EST` format |
| `zoneName` | `neighbourhood` | Area within destination |
| `rates[0].net` | `total_price_usd` | Final price (net includes all) |
| `rates[0].dailyRates[0].dailyNet` | `price_per_night_usd` | Per-night breakdown |
| `rates[0].boardName` | — | Reported in text (no model field yet) |
| `rates[0].cancellationPolicies` | `cancellation_policy` | Summarised into text |
| `latitude`, `longitude` | `latitude`, `longitude` | Direct mapping |

**Prices are final:** Hotelbeds net prices include all supplements and discounts. No additional calculation is needed.

---

## How It Fits in the Agent Architecture

```
Supervisor
    │
    ├── parallel_dispatch
    │       │
    │       └── HotelsAgent
    │               │
    │               ├── search_hotels (Amadeus)
    │               ├── search_hotels_hotelbeds (Hotelbeds)    ← Availability
    │               ├── check_hotel_rate_hotelbeds (Hotelbeds) ← Rate verification
    │               └── search_places_text (Google Places)     ← Enrichment
    │
    ├── BudgetAgent  ← receives hotel costs from HotelsAgent
    └── ItineraryAgent ← uses hotel data for day-by-day plans
```

The `HOTELS_SYSTEM_PROMPT` instructs the agent to:
1. Call **both** Amadeus and Hotelbeds for every search
2. Merge and deduplicate results
3. Call CheckRate for any RECHECK rates
4. Enrich top picks with Google Places (photos, reviews, maps)

---

## Usage Examples

### Basic search (from agent prompt)

```
"Find hotels in Paris for June 15-20, 2 adults"
```

The agent calls:
- `search_hotels_hotelbeds(city_code="PAR", check_in_date="2026-06-15", check_out_date="2026-06-20", adults=2)`
- `search_hotels(city_code="PAR", check_in="2026-06-15", check_out="2026-06-20", adults=2)`

### Family search with filters

```
"Find 4+ star all-inclusive hotels in Cancun for a family with 2 kids (ages 4 and 8)"
```

The agent calls:
- `search_hotels_hotelbeds(city_code="CUN", ..., children=2, children_ages="4,8", min_category=4, board_codes="AI")`

### Rate verification

When availability returns a RECHECK rate:
```
"Check the rate for the Hotel Granvia Kyoto room"
```

The agent calls:
- `check_hotel_rate_hotelbeds(rate_keys="20260615|20260620|W|1|67890|TWN.SU|ID_B2B|BB|MRK1")`

---

## Configuration

In `config/config.yaml`:

```yaml
timeouts:
  hotels: 30  # seconds — covers both Amadeus and Hotelbeds
```

The Hotelbeds tool is part of the `HotelsAgent`, which runs in the parallel dispatch phase (not sequential), so its latency doesn't block other agents.

---

## Board Codes Reference

| Code | Name | Description |
| ---- | ---- | ----------- |
| `RO` | Room Only | No meals included |
| `BB` | Bed & Breakfast | Breakfast included |
| `HB` | Half Board | Breakfast + dinner |
| `FB` | Full Board | Breakfast + lunch + dinner |
| `AI` | All Inclusive | All meals + drinks |
| `TI` | All Inclusive (Soft) | All meals + local drinks |
| `AS` | All Inclusive (Premium) | All meals + premium drinks |

Use these codes with the `board_codes` parameter to filter results.

---

## Error Handling

| HTTP Status | Meaning | Our Handling |
| ----------- | ------- | ------------ |
| 200 | Success | Parse and return results |
| 400 | Bad request (invalid data) | Log + return error message |
| 401 | Auth failed (bad key/signature) | Log + return credential error |
| 403 | Forbidden (account issue) | Log + return error message |
| 410 | Rate expired | CheckRate: return "rate may have expired" |
| 429 | Rate limit exceeded | Retry with exponential backoff (tenacity) |
| 500 | Server error | Retry up to 3 times, then return error |

**Retry logic:** Both tools use `tenacity` with exponential backoff:
- Availability: 3 attempts, max 10s between retries
- CheckRate: 2 attempts, max 8s between retries

---

## Troubleshooting

### "HOTELBEDS_API_KEY and HOTELBEDS_API_SECRET environment variables must be set"

**Cause:** Missing credentials.
**Fix:** Set both `HOTELBEDS_API_KEY` and `HOTELBEDS_API_SECRET` in your `.env` file. Get them from the [Hotelbeds Developer Portal](https://developer.hotelbeds.com).

### "Hotelbeds API error (HTTP 401)"

**Cause:** Invalid API key or signature mismatch.
**Fix:** Verify your API key and secret are correct. The X-Signature uses the current Unix timestamp — ensure your system clock is accurate (NTP synced).

### "Hotelbeds API error (HTTP 429)"

**Cause:** Rate limit exceeded.
**Fix:** The tool retries automatically. If persistent, reduce request frequency or contact Hotelbeds to increase your quota.

### "CheckRate returned no hotel data — the rate may have expired"

**Cause:** The rate key from a previous availability search is no longer valid.
**Fix:** Run a new availability search to get fresh rate keys. Rate keys have limited validity.

### "No hotel offers found on Hotelbeds in XXX"

**Cause:** No availability for the given destination/dates/filters, or the city code is incorrect.
**Fix:** Verify the city code matches a Hotelbeds destination (not all IATA codes map 1:1). Try relaxing filters (remove `min_category`, increase `max_rate`).

---

## API Endpoints Not Yet Implemented

These Hotelbeds Booking API endpoints are available but not yet integrated:

| Endpoint | Method | Purpose | Priority |
| -------- | ------ | ------- | -------- |
| `/bookings` | POST | Confirm a booking | Future (requires payment handling) |
| `/bookings` | GET | List bookings | Future |
| `/bookings/{id}` | GET | Booking details | Future |
| `/bookings/{id}` | PUT | Modify booking | Future |
| `/bookings/{id}` | DELETE | Cancel booking | Future |
| `/bookings/reconfirmations` | GET | Hotel confirmation numbers | Future |

**Content API** endpoints (static hotel data — descriptions, photos, facilities) are also available and would enrich hotel results without additional availability calls.

---

## External Documentation

- [Hotelbeds Booking API Docs](https://developer.hotelbeds.com/documentation/hotels/booking-api/)
- [Hotelbeds Content API Docs](https://developer.hotelbeds.com/documentation/hotels/content-api/)
- [Hotelbeds Cache API Docs](https://developer.hotelbeds.com/documentation/hotels/cache-api/)
- [Hotelbeds API Reference (Swagger)](https://developer.hotelbeds.com/documentation/hotels/booking-api/api-reference/)
- [OpenAPI Spec (local)](APIs/hotelbeds/OpenAPI-Hotel-BookingAPI-3.0.yaml)
