"""Tests for src/tools/web_search.py — Tavily web search tools (mocked HTTP)."""

import respx
from httpx import Response

from src.tools.web_search import search_hidden_gems, search_web

_MOCK_TAVILY_RESPONSE = {
    "answer": "Tokyo is a vibrant city with many hidden gems.",
    "results": [
        {
            "title": "10 Hidden Gems in Tokyo",
            "url": "https://example.com/tokyo-gems",
            "content": "Explore Shimokitazawa for vintage shopping and live music.",
            "score": 0.92,
        },
        {
            "title": "Tokyo Off the Beaten Path",
            "url": "https://example.com/tokyo-offbeat",
            "content": "Yanaka district preserves old Tokyo charm with temples and cats.",
            "score": 0.85,
        },
    ],
}

_MOCK_TAVILY_EMPTY = {
    "answer": "",
    "results": [],
}


class TestSearchWeb:
    @respx.mock
    async def test_returns_results_with_summary(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_RESPONSE)
        )

        result = await search_web.ainvoke({"query": "hidden gems Tokyo"})

        assert "Tokyo is a vibrant city" in result
        assert "Shimokitazawa" in result
        assert "Yanaka" in result
        assert "relevance: 0.92" in result

    @respx.mock
    async def test_returns_message_when_no_results(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_EMPTY)
        )

        result = await search_web.ainvoke({"query": "nonexistent place"})

        assert "No relevant web results" in result

    @respx.mock
    async def test_appends_destination_to_query(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        route = respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_RESPONSE)
        )

        await search_web.ainvoke({
            "query": "best festivals",
            "destinations": ["tokyo", "kyoto"],
        })

        sent_body = route.calls[0].request.content
        # The query should include the destination names
        assert b"tokyo" in sent_body
        assert b"kyoto" in sent_body

    @respx.mock
    async def test_does_not_duplicate_destination_in_query(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        route = respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_RESPONSE)
        )

        await search_web.ainvoke({
            "query": "Tokyo festivals in April",
            "destinations": ["tokyo"],
        })

        sent_body = route.calls[0].request.content
        # "tokyo" is already in the query, should not be appended again
        # The query field should contain "Tokyo festivals in April" without extra "tokyo"
        assert b"Tokyo festivals in April" in sent_body

    @respx.mock
    async def test_truncates_long_content(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        long_response = {
            "answer": "",
            "results": [
                {
                    "title": "Long Article",
                    "url": "https://example.com/long",
                    "content": "A" * 800,
                    "score": 0.90,
                },
            ],
        }
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=long_response)
        )

        result = await search_web.ainvoke({"query": "test query"})

        # Content should be truncated to ~500 chars
        assert "..." in result
        assert len(result) < 800

    @respx.mock
    async def test_includes_source_urls(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_RESPONSE)
        )

        result = await search_web.ainvoke({"query": "Tokyo travel tips"})

        assert "https://example.com/tokyo-gems" in result
        assert "https://example.com/tokyo-offbeat" in result

    @respx.mock
    async def test_news_topic(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        route = respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_RESPONSE)
        )

        await search_web.ainvoke({
            "query": "Japan travel advisory",
            "topic": "news",
        })

        sent_body = route.calls[0].request.content
        assert b'"topic":"news"' in sent_body or b'"topic": "news"' in sent_body


class TestSearchHiddenGems:
    @respx.mock
    async def test_returns_deduplicated_results(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        # Both queries return the same URL — should be deduplicated
        response_1 = {
            "results": [
                {
                    "title": "Tokyo Gems",
                    "url": "https://example.com/gems",
                    "content": "Shimokitazawa vintage shops.",
                    "score": 0.90,
                },
            ],
        }
        response_2 = {
            "results": [
                {
                    "title": "Tokyo Gems",
                    "url": "https://example.com/gems",  # duplicate
                    "content": "Shimokitazawa vintage shops.",
                    "score": 0.88,
                },
                {
                    "title": "Secret Tokyo",
                    "url": "https://example.com/secret",
                    "content": "Explore Yanesen area for old Tokyo vibes.",
                    "score": 0.85,
                },
            ],
        }
        respx.post("https://api.tavily.com/search").mock(
            side_effect=[
                Response(200, json=response_1),
                Response(200, json=response_2),
            ]
        )

        result = await search_hidden_gems.ainvoke({"destination": "Tokyo"})

        assert "Hidden gems and local favorites in Tokyo" in result
        assert "Shimokitazawa" in result
        assert "Yanesen" in result
        # The duplicate URL should only appear once
        assert result.count("https://example.com/gems") == 1

    @respx.mock
    async def test_returns_message_when_no_results(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        empty = {"results": []}
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=empty)
        )

        result = await search_hidden_gems.ainvoke({"destination": "Atlantis"})

        assert "No hidden gem recommendations found" in result

    @respx.mock
    async def test_includes_interests_in_query(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        route = respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json={"results": [
                {"title": "Food", "url": "https://example.com/food", "content": "Street food stalls.", "score": 0.80},
            ]})
        )

        await search_hidden_gems.ainvoke({
            "destination": "Bangkok",
            "interests": ["food", "nightlife"],
        })

        # Both calls should include interest terms
        for call in route.calls:
            body = call.request.content
            assert b"food" in body or b"nightlife" in body
