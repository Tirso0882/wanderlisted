# Duffel API Integration Plan

> **Status**: Research Complete — Ready for Implementation  
> **Author**: AI Assistant  
> **Date**: 2026-05-06  
> **Replaces**: Amadeus Flight Offers Search (current `src/tools/flights.py`)

---

## 1. Executive Summary

Duffel is a modern flights API that aggregates NDC and GDS content from 300+ airlines through a single REST endpoint. It replaces Amadeus as Wanderlisted's flight search provider with advantages in:

- **Simpler authentication** — Bearer token vs OAuth2 client_credentials flow
- **City codes work natively** — `NYC`, `LON`, `TYO` resolve automatically (no IATA lookup needed)
- **Richer data included** — baggage, change/refund conditions, fare brands on every offer
- **No free-tier rate limits** — Amadeus caps at 10 req/s and monthly quotas
- **Better error handling** — clear HTTP errors vs Amadeus proprietary error codes

---

## 2. Architecture: Where Duffel Fits

```
┌─────────────────────────────────────────────────────────┐
│  FlightsAgent (src/agent/agents/flights_agent.py)       │
│  Tools: search_flights, confirm_flight_price            │
└────────────────────────┬────────────────────────────────┘
                         │ calls
┌────────────────────────▼────────────────────────────────┐
│  src/tools/flights_duffel.py  (NEW)                     │
│                                                         │
│  @tool search_flights(...)                              │
│  @tool confirm_flight_price(...)                        │
│  @tool get_cheapest_flight(...)                         │
│  @tool search_cheapest_flight_in_month(...)             │
│                                                         │
│  Internal helpers:                                      │
│    _create_offer_request()                              │
│    _get_offer()                                         │
│    _format_duffel_offer()                               │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP (httpx)
┌────────────────────────▼────────────────────────────────┐
│  Duffel API (api.duffel.com)                            │
│  POST /air/offer_requests                               │
│  GET  /air/offers/:id                                   │
│  GET  /places/suggestions                               │
└─────────────────────────────────────────────────────────┘
```

### Strategy: New file, same tool interface

Create `src/tools/flights_duffel.py` with the same `@tool` signatures as the current `flights.py`. Duffel is the sole flight provider — no toggle needed.

---

## 3. API Reference Summary

### Authentication

```
Authorization: Bearer duffel_test_xxxxx
Duffel-Version: v2
Accept: application/json
Content-Type: application/json
Accept-Encoding: gzip
```

Single token. No refresh. Test tokens start with `duffel_test_`, live with `duffel_live_`.

### Core Endpoints (Search & Price)

| Endpoint | Method | Purpose | Timeout |
|----------|--------|---------|---------|
| `/air/offer_requests` | POST | Search flights | 25s |
| `/air/offers/:id` | GET | Get latest price | 10s |
| `/air/offers/:id/actions/price` | PATCH | Confirm price w/ payment method | 15s |
| `/places/suggestions` | GET | Find airports by lat/lng | 5s |

### Booking Endpoints (Future — when booking enabled)

| Endpoint | Method | Purpose | Timeout |
|----------|--------|---------|---------|
| `/air/orders` | POST | Create booking | 60s |
| `/air/orders/:id` | GET | Retrieve order | 10s |
| `/air/payments` | POST | Pay for held order | 30s |
| `/air/order_cancellations` | POST | Create cancel quote | 15s |
| `/air/order_cancellations/:id/actions/confirm` | POST | Confirm cancel | 15s |
| `/air/order_change_requests` | POST | Request flight change | 15s |
| `/air/order_changes` | POST | Create pending change | 15s |
| `/air/order_changes/:id/actions/confirm` | POST | Confirm change | 30s |

---

## 4. Core Booking Flow

```
1. SEARCH       POST /air/offer_requests
                   ├─ slices: [{origin, destination, departure_date}]
                   ├─ passengers: [{type: "adult"}, {age: 5}]
                   └─ cabin_class: "economy"
                   → Returns: offer_request.offers[]

2. PRICE        GET /air/offers/:offer_id
                   → Returns: offer with latest total_amount/total_currency
                   → Also: conditions (change/refund), payment_requirements

3. BOOK         POST /air/orders
                   ├─ selected_offers: [offer_id]
                   ├─ passengers: [{id, given_name, family_name, born_on, ...}]
                   └─ payments: [{type: "balance", amount, currency}]
                   → Returns: order with booking_reference
```

### For Wanderlisted v1: Steps 1-2 only (search + price confirm)

Booking is Phase 2 — requires commercial Duffel account and payment infrastructure.

---

## 5. Search Best Practices (Mandatory Implementation)

### 5.1 Always Provide `cabin_class`

Reduces results 4-5x. The agent already knows the user's preference from the supervisor profile.

```python
payload = {
    "data": {
        "cabin_class": "economy",  # or business, first, premium_economy
        ...
    }
}
```

### 5.2 Set `max_connections` = 1

Default behavior, but explicit is safer. Keeps results relevant.

```python
payload["data"]["max_connections"] = 1
# Set to 0 for non_stop=True searches
```

### 5.3 Use `supplier_timeout` for speed

```
POST /air/offer_requests?supplier_timeout=15000
```

- 15s for normal searches (balance speed/coverage)
- 10s for "quick look" or multi-date sampling
- 25s for comprehensive searches (user explicitly wants all options)

### 5.4 Use `view=offers` (default flat format)

The flat `offers` format is correct for Wanderlisted because:
- We don't display a grouped UI
- The agent processes results as text, not a hierarchical tree
- Simpler to parse and format

### 5.5 Accept-Encoding: gzip

Always include — reduces payload 3-4x for large result sets.

### 5.6 Limit to 10 offers max

The agent only presents top 5 anyway. Request more than needed to allow post-filtering:

```
POST /air/offer_requests?return_offers=true
```

Then sort/filter the `offers[]` array client-side by price, duration, stops.

---

## 6. Data Mapping: Duffel → FlightSegment/FlightOption

### Duffel Offer → FlightOption

```python
# Duffel offer structure:
{
    "id": "off_xxx",
    "total_amount": "450.00",
    "total_currency": "GBP",
    "owner": { "name": "British Airways", "iata_code": "BA" },
    "slices": [
        {
            "origin": { "iata_code": "JFK", "name": "..." },
            "destination": { "iata_code": "LHR", "name": "..." },
            "duration": "PT7H30M",
            "segments": [
                {
                    "origin": { "iata_code": "JFK" },
                    "destination": { "iata_code": "LHR" },
                    "departing_at": "2026-06-15T19:30:00",
                    "arriving_at": "2026-06-16T07:00:00",
                    "operating_carrier": { "iata_code": "BA", "name": "..." },
                    "operating_carrier_flight_number": "178",
                    "duration": "PT7H30M",
                    "passengers": [
                        {
                            "cabin_class": "economy",
                            "cabin_class_marketing_name": "Economy Basic",
                            "baggages": [
                                { "type": "carry_on", "quantity": 1 },
                                { "type": "checked", "quantity": 0 }
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    "conditions": {
        "change_before_departure": { "allowed": true, "penalty_amount": "50.00", ... },
        "refund_before_departure": { "allowed": false, ... }
    },
    "payment_requirements": {
        "requires_instant_payment": true,
        "price_guarantee_expires_at": null,
        "payment_required_by": null
    }
}
```

### Mapping Table

| Duffel Field | Wanderlisted Field | Notes |
|---|---|---|
| `slices[0].segments` | `FlightOption.outbound` | First slice = outbound |
| `slices[1].segments` | `FlightOption.inbound` | Second slice = return |
| `total_amount` | `FlightOption.total_price_usd` | Convert if not USD |
| `total_currency` | `FlightOption.currency` | |
| `segment.operating_carrier.iata_code` | `FlightSegment.carrier` | |
| `segment.operating_carrier_flight_number` | `FlightSegment.flight_number` | Prefix with carrier |
| `segment.origin.iata_code` | `FlightSegment.departure_airport` | |
| `segment.destination.iata_code` | `FlightSegment.arrival_airport` | |
| `segment.departing_at` | `FlightSegment.departure_time` | |
| `segment.arriving_at` | `FlightSegment.arrival_time` | |
| `segment.duration` | `FlightSegment.duration_minutes` | Parse ISO 8601 |
| `segment.passengers[0].cabin_class` | `FlightSegment.cabin_class` | |
| `len(slice.segments) - 1` | `FlightSegment.stops` | Connections |
| `conditions` | (new field or text output) | Change/refund policies |

---

## 7. Implementation Plan

### Phase 1: Search & Price (replace Amadeus) ✦ PRIORITY

**New file:** `src/tools/flights_duffel.py`

```python
# Tools to implement with same signatures:
@tool search_flights(origin, destination, departure_date, adults, return_date, 
                     children, infants, travel_class, non_stop) -> str

@tool confirm_flight_price(origin, destination, departure_date, ..., offer_index) -> str

@tool get_cheapest_flight(origin, destination, departure_date, ...) -> str

@tool search_cheapest_flight_in_month(origin, destination, year, month, ...) -> str
```

**Key implementation details:**

1. **No IATA lookup needed** — Duffel accepts city codes directly (NYC, LON, TYO)
2. **Include conditions in output** — change/refund info is valuable for the agent
3. **Include baggage info** — segment.passengers[0].baggages shows included bags
4. **Semaphore cap at 5** — same pattern as Amadeus, prevents thundering herd
5. **Retry on 429/5xx** — same tenacity pattern

**Output format enhancement** (include Duffel-exclusive data):
```
  1. BA178 (British Airways) — $450.00 GBP
     Departure: JFK → Arrive: LHR
     Depart: 2026-06-15T19:30 → Arrive: 2026-06-16T07:00
     Duration: 7h 30m (450 minutes) · Non-stop
     Cabin: Economy Basic
     Bags included: 1 carry-on, 0 checked
     Change: Allowed ($50 fee) | Refund: Not allowed
```

### Phase 2: Airport Discovery (enhance search)

**New tool:** `search_nearby_airports`
```python
@tool search_nearby_airports(latitude: float, longitude: float, radius_km: int = 100) -> str
```

Uses `GET /places/suggestions?lat=X&lng=Y&rad=R` to find airports near a point. Useful when a destination doesn't have a major airport.

### Phase 3: Booking (future — requires Duffel commercial account)

- `create_flight_booking` → `POST /air/orders`
- `cancel_flight_booking` → `POST /air/order_cancellations` + confirm
- `change_flight_booking` → order change request flow
- `hold_flight` → create order with `type: "hold"`
- `get_baggage_options` → `GET /air/offers/:id?return_available_services=true`

---

## 8. Environment Variables

```bash
# Required
DUFFEL_ACCESS_TOKEN=duffel_test_xxxxx  # or duffel_live_xxxxx

# Optional
DUFFEL_BASE_URL=https://api.duffel.com   # default
DUFFEL_SUPPLIER_TIMEOUT=15000            # ms, default 15000
```

---

## 9. Error Handling

| HTTP Status | Meaning | Action |
|---|---|---|
| 200 | Success | Process response |
| 400 | Bad request (invalid params) | Return user-friendly message |
| 401 | Invalid/expired token | Fatal — check DUFFEL_ACCESS_TOKEN |
| 404 | Offer expired/not found | "Offer no longer available, search again" |
| 422 | Validation error | Parse `errors[].message` for specifics |
| 429 | Rate limited | Retry with exponential backoff |
| 500+ | Server error | Retry up to 3 times |

Duffel error response format:
```json
{
    "meta": { "status": 422, "request_id": "..." },
    "errors": [
        {
            "type": "validation_error",
            "title": "...",
            "message": "...",
            "code": "..."
        }
    ]
}
```

---

## 10. Key Differences from Amadeus (Migration Notes)

| Aspect | Amadeus | Duffel |
|---|---|---|
| Auth | OAuth2 client_credentials (30min TTL) | Bearer token (no expiry) |
| Search | GET /v2/shopping/flight-offers | POST /air/offer_requests |
| City codes | Sometimes doesn't resolve | Always works (NYC, LON, TYO) |
| Price confirm | POST /v1/shopping/flight-offers/pricing (re-search needed) | GET /air/offers/:id (direct by ID) |
| Baggage | Separate API or missing | Included in segment data |
| Conditions | Not available in search | Included on every offer |
| Rate limits | 10 req/s (free tier), monthly quota | No published hard limit |
| Test env | Different base URL | Same URL, different token prefix |
| Currency | Always returns requested | Returns airline's preferred (may differ) |

---

## 11. Conditions Logic (for Agent Output)

The agent should report flight flexibility when presenting options:

```python
def _format_conditions(conditions: dict | None) -> str:
    """Format change/refund conditions for agent output."""
    if not conditions:
        return "Flexibility: Unknown"
    
    parts = []
    
    change = conditions.get("change_before_departure")
    if change is None:
        parts.append("Change: Unknown")
    elif not change.get("allowed"):
        parts.append("Change: Not allowed")
    elif change.get("penalty_amount") and float(change["penalty_amount"]) > 0:
        parts.append(f"Change: ${change['penalty_amount']} {change.get('penalty_currency', '')} fee")
    else:
        parts.append("Change: Free")
    
    refund = conditions.get("refund_before_departure")
    if refund is None:
        parts.append("Refund: Unknown")
    elif not refund.get("allowed"):
        parts.append("Refund: Not allowed")
    elif refund.get("penalty_amount") and float(refund["penalty_amount"]) > 0:
        parts.append(f"Refund: ${refund['penalty_amount']} {refund.get('penalty_currency', '')} penalty")
    else:
        parts.append("Refund: Free")
    
    return " | ".join(parts)
```

---

## 12. Accurate Pricing Flow (Pre-Booking)

When a user selects a flight and wants to confirm the price:

```python
async def _confirm_price(offer_id: str) -> dict:
    """Get the latest price for an offer (may have changed since search)."""
    # Step 1: Retrieve offer for latest price
    response = await client.get(
        f"{DUFFEL_BASE_URL}/air/offers/{offer_id}",
        headers=headers,
    )
    offer = response.json()["data"]
    # offer["total_amount"] is the current price
    # offer["total_currency"] is the currency
    return offer
```

For card surcharge calculation (Phase 3):
```python
async def _price_with_payment(offer_id: str, card_id: str) -> dict:
    """Price offer including card surcharge."""
    response = await client.patch(
        f"{DUFFEL_BASE_URL}/air/offers/{offer_id}/actions/price",
        json={
            "data": {
                "intended_payment_methods": [
                    {"type": "card", "card_id": card_id}
                ]
            }
        }
    )
    # Response includes surcharge_amount on the payment method
    return response.json()["data"]
```

---

## 13. Baggage Information (Available at Search Time)

Duffel includes baggage in every offer's segments:

```json
"passengers": [{
    "baggages": [
        { "type": "carry_on", "quantity": 1 },
        { "type": "checked", "quantity": 1 }
    ]
}]
```

For extra bags (Phase 3):
```
GET /air/offers/:id?return_available_services=true
```

Returns purchasable baggage services with per-segment, per-passenger pricing.

---

## 14. Hold Orders (Deferred Payment)

Relevant for Phase 3. Some offers allow booking without immediate payment:

```python
# Check if offer supports holding
if not offer["payment_requirements"]["requires_instant_payment"]:
    # Can create hold order
    order = await create_order(offer_id, passengers, type="hold")
    # order["payment_status"]["payment_required_by"] = deadline
    # order["payment_status"]["price_guarantee_expires_at"] = price lock deadline
```

Not all airlines support this. Available for: American Airlines, some legacy carriers.

---

## 15. Cancellation Flow (Phase 3)

```python
# 1. Check cancellable
order = await get_order(order_id)
if "cancel" not in order["available_actions"]:
    return "This order cannot be cancelled via API"

# 2. Get cancellation quote
quote = await create_cancellation(order_id)
# quote["refund_amount"], quote["refund_currency"], quote["refund_to"]
# quote["expires_at"] — must confirm before this time

# 3. Confirm (if user agrees)
await confirm_cancellation(quote["id"])
```

Refund types: `original_form_of_payment` or `airline_credits` (with credit codes).

---

## 16. Order Change Flow (Phase 3)

```python
# 1. Create change request (specify slices to add/remove)
change_request = await create_change_request(
    order_id=order_id,
    slices={
        "remove": [{"slice_id": "sli_xxx"}],  # remove old inbound
        "add": [{"origin": "ATL", "destination": "NYC", "departure_date": "2026-07-01"}]
    }
)

# 2. Review change offers
change_request = await get_change_request(change_request["id"])
# change_request["order_change_offers"] — each has change_total_amount + penalty

# 3. Select and create pending change
pending = await create_order_change(selected_offer_id)

# 4. Confirm (triggers payment of difference + penalty)
confirmed = await confirm_order_change(pending["id"], payment)
```

---

## 17. Test Plan

### Unit Tests (mock with respx)

```python
# tests/test_flights_duffel.py
_MOCK_OFFER_REQUEST_RESPONSE = {
    "data": {
        "id": "orq_test_123",
        "offers": [...],
        "slices": [...],
        "passengers": [...]
    }
}

_MOCK_SINGLE_OFFER = {
    "data": {
        "id": "off_test_456",
        "total_amount": "450.00",
        "total_currency": "USD",
        "owner": {"iata_code": "BA", "name": "British Airways"},
        "slices": [...],
        "conditions": {...}
    }
}
```

### Integration Tests

```python
@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("DUFFEL_ACCESS_TOKEN"), reason="No Duffel token")
async def test_duffel_live_search():
    result = await search_flights.ainvoke({
        "origin": "LHR", "destination": "JFK",
        "departure_date": "2026-08-15", "adults": 1
    })
    assert "LHR" in result or "flights" in result.lower()
```

---

## 18. Migration Checklist

- [x] Create `src/tools/flights_duffel.py` with all 5 tools (search, confirm, cheapest, monthly, nearby airports)
- [x] Add `DUFFEL_ACCESS_TOKEN` to `.env.example`
- [x] FlightsAgent imports directly from `flights_duffel` (no toggle)
- [x] Write unit tests (`tests/test_flights_duffel.py`) with respx mocks
- [ ] Run agent harness: `make harness-agent AGENT=flights`
- [x] Update `conftest.py` with `skip_no_duffel` marker
- [x] Update docs (tools reference, architecture)
- [x] Remove Amadeus entirely (no fallback)
- [ ] Phase 3: Add booking/cancel/change tools (requires commercial account)
