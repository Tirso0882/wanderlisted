"""Tests for src/tools/destination_research.py — composite research tool."""

import time
from unittest.mock import MagicMock, patch

import pytest
import respx
from httpx import Response

from src.tools.destination_research import (
    _cache,
    _CACHE_TTL,
    _cache_key,
    _get_cached,
    _set_cached,
    research_destination,
)


# Reset cache + lazy-init state before each test
@pytest.fixture(autouse=True)
def _reset_state():
    _cache.clear()
    import src.tools.destination_rag as rag_mod
    rag_mod._index = None
    rag_mod._emb_gen = None
    rag_mod._initialised = False
    yield
    _cache.clear()
    rag_mod._index = None
    rag_mod._emb_gen = None
    rag_mod._initialised = False


def _mock_pinecone(matches):
    """Set up a mock Pinecone index + embedding generator."""
    mock_index = MagicMock()
    mock_emb_gen = MagicMock()
    mock_emb_gen.embed_query.return_value = [0.1] * 3072
    mock_index.query.return_value = {"matches": matches}
    return mock_index, mock_emb_gen


_MOCK_TAVILY_RESPONSE = {
    "answer": "Tokyo has amazing street food.",
    "results": [
        {
            "title": "Tokyo Street Food Guide",
            "url": "https://example.com/tokyo-food",
            "content": "Explore Tsukiji Outer Market for fresh sushi.",
            "score": 0.90,
        },
    ],
}

_MOCK_TAVILY_EMPTY = {"answer": "", "results": []}


class TestResearchDestination:
    @respx.mock
    @patch("src.tools.destination_rag.build_index")
    async def test_high_confidence_skips_web(self, mock_build, monkeypatch):
        """When RAG returns high-confidence results, Tavily should NOT be called."""
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        mock_index, mock_emb_gen = _mock_pinecone([
            {"metadata": {"source": "tokyo.md", "text": "Temple etiquette.", "section": "See"}, "score": 0.85},
            {"metadata": {"source": "tokyo.md", "text": "Bow when greeting.", "section": "Culture"}, "score": 0.80},
        ])
        mock_build.return_value = (mock_index, mock_emb_gen)

        # Tavily should NOT be called — no route needed
        tavily_route = respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_RESPONSE)
        )

        result = await research_destination.ainvoke({
            "query": "Tokyo cultural etiquette",
            "destinations": ["tokyo"],
        })

        assert "Temple etiquette" in result
        assert "Sources: guides (high)" in result
        assert tavily_route.call_count == 0

    @respx.mock
    @patch("src.tools.destination_rag.build_index")
    async def test_no_guide_falls_back_to_web(self, mock_build, monkeypatch):
        """When RAG returns nothing, Tavily should be called automatically."""
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        mock_index, mock_emb_gen = _mock_pinecone([])  # No RAG results
        mock_build.return_value = (mock_index, mock_emb_gen)

        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_RESPONSE)
        )

        result = await research_destination.ainvoke({
            "query": "Marrakech culture tips",
            "destinations": ["marrakech"],
        })

        assert "Tsukiji" in result  # From Tavily mock
        assert "Web" in result or "web" in result
        assert "Sources:" in result

    @respx.mock
    @patch("src.tools.destination_rag.build_index")
    async def test_medium_confidence_includes_web(self, mock_build, monkeypatch):
        """Medium RAG confidence should trigger Tavily to complement."""
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        mock_index, mock_emb_gen = _mock_pinecone([
            {"metadata": {"source": "test.md", "text": "Some info.", "section": "See"}, "score": 0.60},
        ])
        mock_build.return_value = (mock_index, mock_emb_gen)

        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_RESPONSE)
        )

        result = await research_destination.ainvoke({
            "query": "test query",
            "destinations": ["test"],
        })

        # Both sources should be present
        assert "Guide" in result or "guide" in result
        assert "Web" in result or "web" in result
        assert "Sources: guides (medium) + web" in result

    @respx.mock
    @patch("src.tools.destination_rag.build_index")
    async def test_tavily_failure_still_returns_rag(self, mock_build, monkeypatch):
        """If Tavily fails, RAG results should still be returned."""
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        mock_index, mock_emb_gen = _mock_pinecone([
            {"metadata": {"source": "test.md", "text": "Good info.", "section": "See"}, "score": 0.55},
        ])
        mock_build.return_value = (mock_index, mock_emb_gen)

        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(500)
        )

        result = await research_destination.ainvoke({
            "query": "test query",
        })

        # RAG results should still be present despite Tavily failure
        assert "Good info." in result

    @respx.mock
    @patch("src.tools.destination_rag.build_index")
    async def test_both_empty_returns_clear_message(self, mock_build, monkeypatch):
        """When both RAG and Tavily return nothing, give a clear message."""
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        mock_index, mock_emb_gen = _mock_pinecone([])
        mock_build.return_value = (mock_index, mock_emb_gen)

        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_EMPTY)
        )

        result = await research_destination.ainvoke({
            "query": "completely unknown place",
        })

        assert "No information found" in result


class TestTavilyCache:
    def test_cache_hit(self):
        _set_cached("test query", "cached result")
        assert _get_cached("test query") == "cached result"

    def test_cache_miss(self):
        assert _get_cached("nonexistent") is None

    def test_cache_ttl_expiry(self):
        key = _cache_key("expired query")
        # Insert with a timestamp far in the past
        _cache[key] = (time.monotonic() - _CACHE_TTL - 1, "stale result")
        assert _get_cached("expired query") is None
        # Entry should be cleaned up
        assert key not in _cache

    def test_cache_eviction_at_max_size(self):
        # Fill cache to max
        for i in range(200):
            _set_cached(f"query-{i}", f"result-{i}")
        assert len(_cache) == 200

        # Adding one more should evict the oldest
        _set_cached("query-new", "result-new")
        assert len(_cache) == 200
        assert _get_cached("query-new") == "result-new"

    @respx.mock
    async def test_cached_tavily_avoids_second_call(self, monkeypatch):
        """Second call to the same query should use cache, not hit Tavily."""
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        route = respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=_MOCK_TAVILY_RESPONSE)
        )

        from src.tools.destination_research import _cached_tavily_search

        # First call — hits Tavily
        result1 = await _cached_tavily_search("Tokyo food guide")
        assert route.call_count == 1
        assert "Tsukiji" in result1

        # Second call — should use cache
        result2 = await _cached_tavily_search("Tokyo food guide")
        assert route.call_count == 1  # Still 1 — no new API call
        assert result1 == result2
