# API Integration Guide

> Patterns and best practices for integrating external APIs into Wanderlisted tools.

---

## Table of Contents

- [Authentication Patterns](#authentication-patterns)
- [HTTP Client Usage](#http-client-usage)
- [Retry & Resilience](#retry--resilience)
- [Response Parsing](#response-parsing)
- [Error Handling](#error-handling)
- [Testing API Integrations](#testing-api-integrations)
- [API Inventory](#api-inventory)

---

## Authentication Patterns

Wanderlisted tools use several authentication mechanisms depending on the API.

### API Key in Header

Most APIs use a simple API key passed in a header.

```python
def _build_headers() -> dict[str, str]:
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    return {"X-Goog-Api-Key": api_key}
```

**Used by:** Google Maps/Places tools, weather, currency, Tavily, safety

### API Key in Query Parameter

Some APIs take the key as a URL parameter.

```python
params = {"key": os.environ["OPENWEATHERMAP_API_KEY"], "q": city}
```

**Used by:** OpenWeatherMap, ExchangeRate API

### SHA-256 Signature (Hotelbeds)

Hotelbeds uses a hash-based signature: `SHA256(api_key + secret + unix_timestamp)`.

```python
import hashlib, time

def _build_headers() -> dict[str, str]:
    api_key = os.environ["HOTELBEDS_API_KEY"]
    secret = os.environ["HOTELBEDS_SECRET"]
    sig = hashlib.sha256(f"{api_key}{secret}{int(time.time())}".encode()).hexdigest()
    return {"Api-key": api_key, "X-Signature": sig, "Accept-Encoding": "gzip"}
```

**Used by:** Hotelbeds Booking API

### OAuth 2.0 Client Credentials (Amadeus)

Amadeus uses a client credentials flow — exchange key+secret for a bearer token.

```python
async def _get_amadeus_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.amadeus.com/v1/security/oauth2/token",
            data={"grant_type": "client_credentials",
                  "client_id": os.environ["AMADEUS_API_KEY"],
                  "client_secret": os.environ["AMADEUS_API_SECRET"]},
        )
        return resp.json()["access_token"]
```

**Used by:** Amadeus Flights, Amadeus Hotels

### No Authentication

Some tools compute locally or use free APIs.

**Used by:** `calculate_budget` (pure computation), `lookup_iata_code` (local CSV), REST Countries API

---

## HTTP Client Usage

All tools use **`httpx.AsyncClient`** for HTTP. Key patterns:

### Basic GET

```python
async with httpx.AsyncClient() as client:
    resp = await client.get(url, headers=headers, params=params, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
```

### POST with JSON Body

```python
async with httpx.AsyncClient() as client:
    resp = await client.post(url, headers=headers, json=body, timeout=30.0)
    resp.raise_for_status()
```

### Rules

| Rule | Reason |
|------|--------|
| Always set `timeout` | Prevent hanging on unresponsive APIs |
| Use `async with` context manager | Ensures connection cleanup |
| Call `resp.raise_for_status()` | Converts 4xx/5xx to exceptions |
| Use `params=` for query strings | Proper URL encoding |
| Use `json=` for POST bodies | Automatic serialization + Content-Type |

### Timeouts

Timeouts are configured in `config/config.yaml` under `timeouts:` and should be referenced from there when possible. As a fallback, hardcode a reasonable default:

| Tool Category | Typical Timeout |
|---------------|-----------------|
| Search APIs (flights, hotels) | 30s |
| Google Maps APIs | 15-25s |
| Weather, currency | 10s |

---

## Retry & Resilience

Use **`tenacity`** for retrying transient failures (network errors, 502/503/429).

### Standard Pattern

```python
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception_type(httpx.RequestError),
)
async def _call_api(...) -> dict:
    ...
```

### What to retry

| Retry | Don't Retry |
|-------|-------------|
| `httpx.RequestError` (network) | `httpx.HTTPStatusError` 400–499 (client error) |
| `httpx.ReadTimeout` | 401/403 (auth failure) |
| HTTP 429 (rate limit) | 404 (not found) |
| HTTP 502, 503, 504 | Business logic errors |

### Rate Limiting

For APIs with rate limits (Hotelbeds: 50 req/s, Amadeus: 1 req/100ms on test):
- Tenacity handles these via `wait_exponential`
- Do not add explicit `sleep()` calls
- Let the retry mechanism handle backoff naturally

---

## Response Parsing

Tools must convert raw API JSON into **human-readable text** for the LLM.

### Principles

1. **Extract only what the LLM needs** — don't dump full JSON
2. **Format for readability** — use bullets, labels, and line breaks
3. **Include actionable data** — prices, names, dates, links
4. **Limit result count** — return top 5-8 results, not hundreds
5. **Preserve keys for downstream tools** — e.g., `rateKey` for CheckRate

### Example: Hotel Results

```python
lines = []
for hotel in hotels[:8]:
    name = hotel.get("name", "Unknown Hotel")
    stars = hotel.get("categoryName", "")
    price = f"${float(hotel.get('minRate', 0)):.2f}"
    lines.append(f"  {name} ({stars}) — from {price}/night")
    lines.append(f"    Rate key: {hotel.get('rateKey', 'N/A')}")
return "\n".join(lines)
```

### Nested Data Extraction

Many APIs return deeply nested JSON. Use `.get()` chains with defaults:

```python
# Safe nested access
city = hotel.get("address", {}).get("city", "Unknown")
lat = hotel.get("location", {}).get("latitude")
```

---

## Error Handling

### Pattern: Catch → Log → Return Friendly Message

```python
@tool
async def my_tool(param: str) -> str:
    try:
        data = await _call_api(param)
    except httpx.HTTPStatusError as e:
        logger.error("HTTP %s: %s", e.response.status_code, e.response.text[:300])
        return f"API error (HTTP {e.response.status_code})."
    except httpx.RequestError as e:
        logger.error("Request error: %s", e)
        return f"Could not reach the API: {e}"
    except RuntimeError as e:
        return str(e)
    ...
```

### Error Return Rules

| Do | Don't |
|----|-------|
| Return `"No flights found for those dates."` | Return raw stack traces |
| Return `"API error (HTTP 429). Try again."` | Raise `Exception` to the LLM |
| Log full error details with `logger.error()` | Use `print()` for error output |
| Include HTTP status code in message | Return empty string `""` |

### Missing Credentials

Check for required env vars early and return immediately:

```python
api_key = os.environ.get("MY_API_KEY", "")
if not api_key:
    return "MY_API_KEY environment variable is not set."
```

---

## Testing API Integrations

See the [Tool Development Guide](TOOL_DEVELOPMENT_GUIDE.md) for complete test templates. Key points specific to API testing:

### Mock External Calls with respx

```python
import respx
from httpx import Response

@respx.mock
async def test_api_call(self, monkeypatch):
    monkeypatch.setenv("API_KEY", "test")
    respx.get("https://api.example.com/endpoint").mock(
        return_value=Response(200, json={"results": [...]})
    )
    result = await my_tool.ainvoke({"param": "test"})
    assert "expected text" in result
```

### Mock Pattern: Match Any URL in a Domain

```python
respx.get(url__startswith="https://api.amadeus.com/").mock(...)
```

### OAuth Token Mocking

For Amadeus-style token flows, mock the token endpoint too:

```python
respx.post("https://api.amadeus.com/v1/security/oauth2/token").mock(
    return_value=Response(200, json={"access_token": "test-token"})
)
```

---

## API Inventory

| API | Provider | Auth | Tools Using It | Env Vars |
|-----|----------|------|---------------|----------|
| Amadeus Flight Offers v2 | Amadeus | OAuth2 | `search_flights` | `AMADEUS_API_KEY`, `AMADEUS_API_SECRET` |
| Amadeus Hotel v1/v3 | Amadeus | OAuth2 | `search_hotels` | `AMADEUS_API_KEY`, `AMADEUS_API_SECRET` |
| Hotelbeds Booking API | Hotelbeds | SHA-256 sig | `search_hotels_hotelbeds`, `check_hotel_rate_hotelbeds` | `HOTELBEDS_API_KEY`, `HOTELBEDS_SECRET` |
| Google Places (New) | Google Cloud | API key | `search_activities`, `search_places_nearby`, `search_places_text` | `GOOGLE_MAPS_API_KEY` |
| Google Directions | Google Cloud | API key | `get_directions` | `GOOGLE_MAPS_API_KEY` |
| Google Distance Matrix | Google Cloud | API key | `get_distance_matrix` | `GOOGLE_MAPS_API_KEY` |
| Google Routes | Google Cloud | API key | `compute_route`, `optimize_day_route` | `GOOGLE_MAPS_API_KEY` |
| Google Time Zone | Google Cloud | API key | `get_timezone` | `GOOGLE_MAPS_API_KEY` |
| OpenWeatherMap Forecast | OpenWeatherMap | API key (param) | `get_weather` | `OPENWEATHERMAP_API_KEY` |
| ExchangeRate API v6 | exchangerate-api.com | API key (URL) | `convert_currency` | `EXCHANGE_RATE_API_KEY` |
| REST Countries v3.1 | restcountries.com | None | `get_safety_info` | *(none)* |
| Tavily Search | Tavily | API key | `search_web`, `search_hidden_gems`, `research_destination` | `TAVILY_API_KEY` |
| Pinecone | Pinecone | API key | `search_destination_guides`, `research_destination` | `PINECONE_API_KEY` |
| Cohere Rerank v3.5 | Cohere | API key | `research_destination` | `COHERE_API_KEY` |
| Azure OpenAI | Microsoft | API key | All agents (LLM) | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` |
