import os

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def _fetch_weather_api(city: str, days: int, api_key: str) -> dict:
    """Call OpenWeatherMap with retry logic."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={
                "q": city,
                "cnt": days * 8,
                "appid": api_key,
                "units": "metric",
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()


@tool
async def get_weather(city: str, days: int = 5) -> str:
    """Get weather forecast for a city. Returns temperature, conditions, and
    precipitation probability for upcoming days.

    Args:
        city: City name (e.g., "Tokyo", "Paris", "New York")
        days: Number of days to forecast (1-5, default 5)
    """
    api_key = os.environ["OPENWEATHER_API_KEY"]
    days = max(1, min(days, 5))
    data = await _fetch_weather_api(city, days, api_key)

    # Aggregate 3-hour intervals into daily summaries
    daily: dict[str, dict] = {}
    for item in data["list"]:
        date = item["dt_txt"].split(" ")[0]
        if date not in daily:
            daily[date] = {"temps": [], "descriptions": [], "rain_prob": []}
        daily[date]["temps"].append(item["main"]["temp"])
        daily[date]["descriptions"].append(item["weather"][0]["description"])
        if "pop" in item:
            daily[date]["rain_prob"].append(item["pop"])

    lines = [f"Weather forecast for {city}:"]
    for date, info in list(daily.items())[:days]:
        low = min(info["temps"])
        high = max(info["temps"])
        condition = max(set(info["descriptions"]), key=info["descriptions"].count)
        rain = int(max(info["rain_prob"], default=0) * 100)
        lines.append(
            f"  {date}: {low:.0f}–{high:.0f}°C, {condition}, {rain}% rain chance"
        )

    return "\n".join(lines)
