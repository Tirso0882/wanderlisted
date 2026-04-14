"""Tavily-powered web search for real-time travel intelligence."""

import os
from typing import Optional

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from custom_logging import AppLogger

logger = AppLogger(logger_name="tools.web_search", level="DEBUG")

_TAVILY_BASE = "https://api.tavily.com"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def _tavily_search(
    query: str,
    *,
    max_results: int = 5,
    search_depth: str = "advanced",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    topic: str = "general",
) -> dict:
    """Call Tavily Search API with retry logic."""
    api_key = os.environ["TAVILY_API_KEY"]
    payload: dict = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": True,
        "topic": topic,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{_TAVILY_BASE}/search",
            json=payload,
            timeout=15.0,
        )
        response.raise_for_status()
        return response.json()


@tool
async def search_web(
    query: str,
    destinations: Optional[list[str]] = None,
    topic: str = "general",
) -> str:
    """Search the web for real-time travel information using Tavily.

    Use this tool to find CURRENT information that static guides cannot
    provide: recent blog posts, trending spots, upcoming events and
    festivals, newly opened restaurants, travel advisories, hidden gems
    recommended by locals, and up-to-date prices.

    Best for:
    - "hidden gems in [city] 2026" — discover off-the-beaten-path spots
    - "festivals in [city] [month] [year]" — find current events
    - "best new restaurants [city]" — recently opened or trending venues
    - "travel tips [city] reddit" — authentic community recommendations
    - "[city] neighborhoods locals recommend" — areas tourists miss
    - "current travel advisory [country]" — up-to-date safety info

    Args:
        query: Natural language search query. Be specific and include the
               destination name. Adding "2026", "hidden gem", "local
               favorite", or "off the beaten path" improves results.
        destinations: Optional destination names to auto-append to the query
                      if not already included.
        topic: Search topic — "general" (default) or "news" for recent events.
    """
    # Enrich the query with destination names if they're missing
    query_lower = query.lower()
    if destinations:
        missing = [d for d in destinations if d.lower() not in query_lower]
        if missing:
            query = f"{query} {' '.join(missing)}"

    logger.debug(f"Web search: {query!r}, topic={topic}")

    data = await _tavily_search(
        query,
        max_results=5,
        search_depth="advanced",
        topic=topic,
        exclude_domains=["tripadvisor.com"],  # Often blocks scraping
    )

    answer = data.get("answer", "")
    results = data.get("results", [])

    if not results and not answer:
        return "No relevant web results found for this query."

    sections: list[str] = []

    if answer:
        sections.append(f"**Summary:** {answer}")

    for i, result in enumerate(results, 1):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        content = result.get("content", "")
        score = result.get("score", 0)

        # Truncate overly long snippets
        if len(content) > 500:
            content = content[:497] + "..."

        sections.append(
            f"[{i}] {title} (relevance: {score:.2f})\n    Source: {url}\n    {content}"
        )

    logger.info(f"Web search '{query[:60]}' → {len(results)} result(s)")
    return "\n\n".join(sections)


@tool
async def search_hidden_gems(
    destination: str,
    interests: Optional[list[str]] = None,
) -> str:
    """Search the web specifically for hidden gems, local favorites, and
    off-the-beaten-path experiences at a destination.

    This tool crafts optimized queries targeting authentic local
    recommendations from travel blogs, Reddit, and community forums.

    Use this AFTER search_destination_guides to complement curated knowledge
    with fresh, crowd-sourced discoveries.

    Args:
        destination: City or region name (e.g. "Tokyo", "Barcelona").
        interests: Optional list of interest areas to focus the search,
                   e.g. ["food", "street art", "nightlife", "nature"].
    """
    interest_str = ""
    if interests:
        interest_str = " " + " ".join(interests)

    queries = [
        f"hidden gems {destination}{interest_str} locals recommend",
        f"{destination} off the beaten path underrated spots{interest_str}",
    ]

    logger.debug(f"Hidden gems search: {destination!r}, interests={interests!r}")

    all_sections: list[str] = []
    seen_urls: set[str] = set()

    for q in queries:
        data = await _tavily_search(
            q,
            max_results=4,
            search_depth="advanced",
            exclude_domains=["tripadvisor.com"],
        )

        for result in data.get("results", []):
            url = result.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = result.get("title", "Untitled")
            content = result.get("content", "")
            score = result.get("score", 0)

            if len(content) > 500:
                content = content[:497] + "..."

            all_sections.append(
                f"- {title} (relevance: {score:.2f})\n  Source: {url}\n  {content}"
            )

    if not all_sections:
        return f"No hidden gem recommendations found for {destination}."

    # Limit to top 6 unique results
    all_sections = all_sections[:6]

    logger.info(f"Hidden gems '{destination}' → {len(all_sections)} result(s)")
    header = f"Hidden gems and local favorites in {destination}:"
    return header + "\n\n" + "\n\n".join(all_sections)
