import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def _fetch_country_info(country_name: str) -> list:
    """Call REST Countries API with retry logic."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://restcountries.com/v3.1/name/{country_name}",
            params={
                "fields": "name,capital,region,subregion,languages,"
                "currencies,population,timezones"
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()


@tool
async def get_safety_info(country_name: str) -> str:
    """Get travel safety and general information for a country including region,
    languages, currency, population, and practical travel notes.

    Args:
        country_name: Full country name (e.g., "Japan", "France", "Brazil")
    """
    data = await _fetch_country_info(country_name)

    if not data:
        return f"No information found for '{country_name}'."

    country = data[0]
    name = country.get("name", {}).get("common", country_name)
    capital = ", ".join(country.get("capital", ["Unknown"]))
    region = country.get("region", "Unknown")
    subregion = country.get("subregion", "Unknown")
    languages = ", ".join(country.get("languages", {}).values()) or "Unknown"

    currencies = country.get("currencies", {})
    currency_parts = []
    for code, info in currencies.items():
        symbol = info.get("symbol", "?")
        currency_parts.append(f"{info.get('name', code)} ({code}, symbol: {symbol})")
    currency_str = ", ".join(currency_parts) or "Unknown"

    population = country.get("population", 0)
    timezones = ", ".join(country.get("timezones", ["Unknown"]))

    return (
        f"Country: {name}\n"
        f"Capital: {capital}\n"
        f"Region: {region} — {subregion}\n"
        f"Languages: {languages}\n"
        f"Currency: {currency_str}\n"
        f"Population: {population:,}\n"
        f"Timezones: {timezones}\n"
        f"\nTravel Notes:\n"
        f"- Check your country's travel advisory for {name} before traveling\n"
        f"- Verify visa requirements for your nationality\n"
        f"- Ensure passport is valid for at least 6 months beyond travel dates\n"
        f"- Register with your embassy when traveling abroad"
    )
