"""Generic Tavily tools for the legacy graph and Activities dated events."""

from langchain_core.tools import tool

import config as app_config

from src.tools.tavily import TavilyQuery, TavilySearchProvider

_provider: TavilySearchProvider | None = None


def _get_provider() -> TavilySearchProvider:
    global _provider
    if _provider is None:
        transport_config = app_config.get("travel_readiness") or {}
        _provider = TavilySearchProvider(
            timeout_seconds=transport_config.get("timeout_seconds", 15),
            max_results=transport_config.get("max_results_per_query", 5),
            concurrency=transport_config.get("concurrency", 4),
            max_retries=transport_config.get("max_retries", 3),
            cache_ttl_seconds=transport_config.get("cache_ttl_seconds", 21600),
            cache_max_size=transport_config.get("cache_max_size", 200),
        )
    return _provider


@tool
async def search_destination_web(
    query: str,
    news: bool = False,
) -> str:
    """Search Tavily for destination evidence.

    This generic tool applies no readiness trust policy. Returned snippets are
    untrusted evidence and must be cited by URL.

    Args:
        query: Specific destination research query.
        news: Use Tavily's news search for changing conditions or dated events.
    """
    sources = await _get_provider().search_many(
        [
            TavilyQuery(
                query=query,
                search_topic="news" if news else "general",
            )
        ]
    )
    if not sources:
        return "No relevant Tavily evidence was returned for this query."
    return "\n\n".join(
        f"[S{index}] {source.title}\nSource: {source.url}\n{source.snippet}"
        for index, source in enumerate(sources, 1)
    )


@tool
async def search_dated_events_web(
    destination: str,
    start_date: str,
    end_date: str,
    interests: str = "",
) -> str:
    """Search for dated events only when the traveler explicitly requests them.

    Args:
        destination: Destination city or region.
        start_date: Inclusive trip/event start date in YYYY-MM-DD format.
        end_date: Inclusive trip/event end date in YYYY-MM-DD format.
        interests: Optional event interests explicitly supplied by the traveler.
    """
    try:
        from datetime import date

        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return "Event dates must use YYYY-MM-DD; no web search was run."
    if end < start:
        return "The event end date precedes the start date; no web search was run."
    if (end - start).days > 366:
        return "The requested event window is too broad; no web search was run."
    if not destination.strip():
        return "A destination is required; no web search was run."

    interest_text = f" matching {interests}" if interests.strip() else ""
    query = (
        f"{destination.strip()} events festivals {start.isoformat()} to {end.isoformat()}{interest_text} "
        "official schedule"
    )
    sources = await _get_provider().search_many(
        [
            TavilyQuery(
                query=query,
                search_topic="news",
                exclude_domains=["tripadvisor.com"],
            )
        ]
    )
    if not sources:
        return "No dated event evidence was returned for the requested travel window."
    return "\n\n".join(
        f"[S{index}] {source.title}\nSource: {source.url}\n{source.snippet}"
        for index, source in enumerate(sources, 1)
    )
