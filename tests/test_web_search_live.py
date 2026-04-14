"""Live integration tests for Tavily web search tools.

Run with:  pytest tests/test_web_search_live.py -v -m integration
Requires:  TAVILY_API_KEY in .env
"""

import os

import pytest

from src.tools.web_search import search_hidden_gems, search_web

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _require_tavily_key():
    if not os.environ.get("TAVILY_API_KEY"):
        pytest.skip("TAVILY_API_KEY not set")


class TestSearchWebLive:
    async def test_basic_travel_query(self):
        result = await search_web.ainvoke(
            {
                "query": "best time to visit Tokyo 2026",
            }
        )

        assert len(result) > 50
        assert "No relevant web results" not in result
        # Should contain at least one source URL
        assert "http" in result

    async def test_destination_scoped_query(self):
        result = await search_web.ainvoke(
            {
                "query": "festivals and events April",
                "destinations": ["barcelona"],
            }
        )

        assert len(result) > 50
        assert "No relevant web results" not in result

    async def test_news_topic(self):
        result = await search_web.ainvoke(
            {
                "query": "Japan travel advisory",
                "topic": "news",
            }
        )

        assert len(result) > 20
        assert "http" in result


class TestSearchHiddenGemsLive:
    async def test_hidden_gems_with_interests(self):
        result = await search_hidden_gems.ainvoke(
            {
                "destination": "Tokyo",
                "interests": ["food", "street art"],
            }
        )

        assert len(result) > 50
        assert "Hidden gems" in result or "http" in result
        assert "No hidden gem recommendations" not in result

    async def test_hidden_gems_uncovered_destination(self):
        """Test a destination that likely has NO curated RAG guide."""
        result = await search_hidden_gems.ainvoke(
            {
                "destination": "Marrakech",
            }
        )

        assert len(result) > 50
        assert "No hidden gem recommendations" not in result
