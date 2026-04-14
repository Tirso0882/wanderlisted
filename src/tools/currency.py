import os

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def _fetch_exchange_rate(
    api_key: str, from_currency: str, to_currency: str, amount: float
) -> dict:
    """Call ExchangeRate API with retry logic."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://v6.exchangerate-api.com/v6/{api_key}/pair/"
            f"{from_currency}/{to_currency}/{amount}",
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()


@tool
async def convert_currency(from_currency: str, to_currency: str, amount: float) -> str:
    """Convert an amount from one currency to another using live exchange rates.

    Args:
        from_currency: Source currency code (e.g., "USD", "EUR", "GBP")
        to_currency: Target currency code (e.g., "JPY", "USD", "EUR")
        amount: Amount to convert
    """
    api_key = os.environ["EXCHANGERATE_API_KEY"]
    data = await _fetch_exchange_rate(api_key, from_currency, to_currency, amount)

    if data.get("result") != "success":
        return f"Currency conversion failed: {data.get('error-type', 'unknown error')}"

    converted = data["conversion_result"]
    rate = data["conversion_rate"]
    return (
        f"{amount:,.2f} {from_currency} = {converted:,.2f} {to_currency}\n"
        f"Exchange rate: 1 {from_currency} = {rate:,.4f} {to_currency}\n"
        f"Last updated: {data.get('time_last_update_utc', 'N/A')}"
    )
