"""Activities-owned dated-event search boundary tests."""

from unittest.mock import AsyncMock

from src.tools import web_search
from src.tools.tavily import TavilySource


async def test_invalid_event_dates_do_not_spend_a_provider_call(monkeypatch):
    provider = AsyncMock()
    monkeypatch.setattr(web_search, "_get_provider", lambda: provider)

    result = await web_search.search_dated_events_web.ainvoke(
        {
            "destination": "Paris",
            "start_date": "next week",
            "end_date": "2026-08-10",
        }
    )

    assert "YYYY-MM-DD" in result
    provider.search_many.assert_not_awaited()


async def test_valid_event_search_is_one_bounded_news_query(monkeypatch):
    provider = AsyncMock()
    provider.search_many.return_value = [
        TavilySource(
            title="Official schedule",
            url="https://events.example/schedule",
            domain="events.example",
            snippet="Festival on August 5.",
            query="Paris events",
        )
    ]
    monkeypatch.setattr(web_search, "_get_provider", lambda: provider)

    result = await web_search.search_dated_events_web.ainvoke(
        {
            "destination": "Paris",
            "start_date": "2026-08-01",
            "end_date": "2026-08-10",
            "interests": "jazz",
        }
    )

    queries = provider.search_many.await_args.args[0]
    assert len(queries) == 1
    assert queries[0].search_topic == "news"
    assert queries[0].include_domains == []
    assert "jazz" in queries[0].query
    assert "https://events.example/schedule" in result
