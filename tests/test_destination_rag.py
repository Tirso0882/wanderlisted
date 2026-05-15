"""Tests for src/tools/destination_rag.py — RAG search tool (Pinecone backend).

Tests multi-tenant namespace retrieval, reranking fallback, and confidence
level classification.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.destination_rag import search_destination_guides


# Reset the lazy-init state before each test
@pytest.fixture(autouse=True)
def _reset_index():
    import src.tools.destination_rag as mod

    mod._index = None
    mod._emb_gen = None
    mod._initialised = False
    yield
    mod._index = None
    mod._emb_gen = None
    mod._initialised = False


def _make_pinecone_response(matches):
    """Build a Pinecone-style query response dict."""
    return {"matches": matches}


def _setup_mocks(mock_build, matches, namespace_matches=None):
    """Configure mock index + emb_gen; optionally return different results per namespace."""
    mock_index = MagicMock()
    mock_emb_gen = MagicMock()
    mock_emb_gen.embed_query.return_value = [0.1] * 3072

    if namespace_matches:
        # Return different results based on the namespace kwarg
        def _query_side_effect(**kwargs):
            ns = kwargs.get("namespace", "")
            if ns in namespace_matches:
                return _make_pinecone_response(namespace_matches[ns])
            return _make_pinecone_response(matches)
        mock_index.query.side_effect = _query_side_effect
    else:
        mock_index.query.return_value = _make_pinecone_response(matches)

    mock_build.return_value = (mock_index, mock_emb_gen)
    return mock_index, mock_emb_gen


class TestSearchDestinationGuides:
    @patch("src.tools.destination_rag.build_index")
    async def test_returns_relevant_content(self, mock_build):
        mock_index, mock_emb_gen = _setup_mocks(
            mock_build,
            [
                {
                    "metadata": {
                        "source": "japan_guide.md",
                        "text": "Visit Fushimi Inari early morning to avoid crowds.",
                        "section": "See",
                    },
                    "score": 0.92,
                },
                {
                    "metadata": {
                        "source": "japan_guide.md",
                        "text": "Try conveyor-belt sushi for affordable options.",
                        "section": "Eat",
                    },
                    "score": 0.87,
                },
            ],
        )

        result = await search_destination_guides.ainvoke("Kyoto temple tips")

        assert "Fushimi Inari" in result
        assert "conveyor-belt sushi" in result
        assert "japan_guide.md" in result
        assert "Guide confidence: high" in result
        mock_emb_gen.embed_query.assert_called()

    @patch("src.tools.destination_rag.build_index")
    async def test_returns_message_when_no_guides(self, mock_build):
        mock_build.return_value = None

        result = await search_destination_guides.ainvoke("anything")

        assert "No destination guides" in result

    @patch("src.tools.destination_rag.build_index")
    async def test_returns_message_when_no_results(self, mock_build):
        _setup_mocks(mock_build, [])

        result = await search_destination_guides.ainvoke("alien planet travel")

        assert "No relevant destination guide content" in result
        assert "search_web" in result or "search_hidden_gems" in result

    @patch("src.tools.destination_rag.build_index")
    async def test_formats_multiple_sources(self, mock_build):
        _setup_mocks(
            mock_build,
            [
                {
                    "metadata": {
                        "source": "japan_guide.md",
                        "text": "Tokyo info",
                        "section": "See",
                    },
                    "score": 0.90,
                },
                {
                    "metadata": {
                        "source": "france_guide.md",
                        "text": "Paris info",
                        "section": "See",
                    },
                    "score": 0.85,
                },
            ],
        )

        result = await search_destination_guides.ainvoke("city tips")

        assert "japan_guide.md" in result
        assert "france_guide.md" in result
        assert "---" in result

    @patch("src.tools.destination_rag.build_index")
    async def test_includes_section_in_output(self, mock_build):
        """Output should include the section metadata."""
        _setup_mocks(
            mock_build,
            [
                {
                    "metadata": {
                        "source": "japan_guide.md",
                        "text": "Sushi tips",
                        "section": "Eat",
                    },
                    "score": 0.90,
                },
            ],
        )

        result = await search_destination_guides.ainvoke("food tips")
        assert "section: Eat" in result

    @patch("src.tools.destination_rag.build_index")
    async def test_lazy_init_calls_build_once(self, mock_build):
        _setup_mocks(
            mock_build,
            [
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Test",
                        "section": "intro",
                    },
                    "score": 0.80,
                },
            ],
        )

        await search_destination_guides.ainvoke("query 1")
        await search_destination_guides.ainvoke("query 2")

        # build_index should only be called once (lazy init)
        mock_build.assert_called_once()

    @patch("src.tools.destination_rag.build_index")
    async def test_filters_low_relevance_matches(self, mock_build):
        """Matches below _MIN_RELEVANCE (0.40) should be excluded."""
        _setup_mocks(
            mock_build,
            [
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Good match",
                        "section": "See",
                    },
                    "score": 0.75,
                },
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Noisy match",
                        "section": "Eat",
                    },
                    "score": 0.30,
                },
            ],
        )

        result = await search_destination_guides.ainvoke("test query")

        assert "Good match" in result
        assert "Noisy match" not in result

    @patch("src.tools.destination_rag.build_index")
    async def test_low_confidence_includes_web_nudge(self, mock_build):
        """Low-confidence results should nudge agent to use web search."""
        _setup_mocks(
            mock_build,
            [
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Weak match",
                        "section": "See",
                    },
                    "score": 0.48,
                },
            ],
        )

        result = await search_destination_guides.ainvoke("obscure topic")

        assert "Guide confidence: low" in result
        assert "search_web" in result

    @patch("src.tools.destination_rag.build_index")
    async def test_medium_confidence_includes_complement_hint(self, mock_build):
        """Medium-confidence results should suggest complementing with web search."""
        _setup_mocks(
            mock_build,
            [
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Decent match",
                        "section": "See",
                    },
                    "score": 0.60,
                },
            ],
        )

        result = await search_destination_guides.ainvoke("moderate topic")

        assert "Guide confidence: medium" in result
        assert "search_web" in result

    @patch("src.tools.destination_rag.build_index")
    async def test_top_k_parameter(self, mock_build):
        """Custom top_k should be passed to Pinecone query."""
        mock_index, _ = _setup_mocks(
            mock_build,
            [
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Result",
                        "section": "See",
                    },
                    "score": 0.80,
                },
            ],
        )

        await search_destination_guides.ainvoke({"query": "test", "top_k": 8})

        # Verify that query was called with the expected top_k
        assert mock_index.query.call_count >= 1
        call_kwargs = mock_index.query.call_args
        assert call_kwargs.kwargs.get("top_k") == 8 or call_kwargs[1].get("top_k") == 8


class TestMultiTenantRetrieval:
    """Tests for multi-tenant namespace support."""

    @patch("src.tools.destination_rag.build_index")
    async def test_no_tenant_uses_wikivoyage_namespace(self, mock_build):
        """Without tenant, should query the wikivoyage namespace."""
        mock_index, _ = _setup_mocks(
            mock_build,
            [
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Wiki content",
                        "section": "See",
                    },
                    "score": 0.80,
                },
            ],
        )

        await search_destination_guides.ainvoke({"query": "test"})

        # Should query wikivoyage/destination_guides
        call_kwargs = mock_index.query.call_args
        assert "wikivoyage" in call_kwargs.kwargs.get("namespace", call_kwargs[1].get("namespace", ""))

    @patch("src.tools.destination_rag.build_index")
    async def test_tenant_searches_client_namespace_first(self, mock_build):
        """With tenant, should query client namespace before wikivoyage."""
        client_matches = [
            {
                "metadata": {
                    "source": "branded_guide.md",
                    "text": "Our premium Tokyo tour package",
                    "section": "See",
                },
                "score": 0.90,
            },
        ] * 5  # Enough to fill top_k

        mock_index, _ = _setup_mocks(
            mock_build,
            [],
            namespace_matches={
                "acme_travel/destination_guides": client_matches,
                "wikivoyage/destination_guides": [],
            },
        )

        result = await search_destination_guides.ainvoke({
            "query": "Tokyo tours",
            "tenant": "acme_travel",
        })

        assert "premium Tokyo tour" in result

    @patch("src.tools.destination_rag.build_index")
    async def test_tenant_falls_back_to_wikivoyage(self, mock_build):
        """When client namespace has insufficient results, wikivoyage fills gaps."""
        mock_index, _ = _setup_mocks(
            mock_build,
            [],
            namespace_matches={
                "acme_travel/destination_guides": [
                    {
                        "metadata": {
                            "source": "client.md",
                            "text": "Client result",
                            "section": "See",
                        },
                        "score": 0.85,
                    },
                ],
                "wikivoyage/destination_guides": [
                    {
                        "metadata": {
                            "source": "wiki.md",
                            "text": "Wiki fallback result",
                            "section": "Eat",
                        },
                        "score": 0.75,
                    },
                ],
            },
        )

        result = await search_destination_guides.ainvoke({
            "query": "Tokyo tips",
            "tenant": "acme_travel",
        })

        assert "Client result" in result
        assert "Wiki fallback result" in result

    @patch("src.tools.destination_rag.build_index")
    async def test_output_includes_content_tier(self, mock_build):
        """Results should show whether they came from client or community tier."""
        _setup_mocks(
            mock_build,
            [
                {
                    "metadata": {
                        "source": "wiki.md",
                        "text": "Community content",
                        "section": "See",
                        "content_tier": "community",
                    },
                    "score": 0.80,
                },
            ],
        )

        result = await search_destination_guides.ainvoke("test query")
        assert "tier:" in result


class TestPineconeFailureGracefulDegradation:
    """Tests that Pinecone failures (auth, network, etc.) are handled gracefully."""

    @patch("src.tools.destination_rag.build_index")
    async def test_build_index_exception_returns_no_guides(self, mock_build):
        """When build_index raises (e.g. Pinecone 401), return a friendly message."""
        mock_build.side_effect = Exception("(401) Unauthorized: Invalid API Key")

        result = await search_destination_guides.ainvoke("Kyoto temple tips")

        assert "No destination guides" in result

    @patch("src.tools.destination_rag.build_index")
    async def test_build_index_exception_sets_initialised_flag(self, mock_build):
        """After a failed init, subsequent calls should not retry build_index."""
        import src.tools.destination_rag as mod

        mock_build.side_effect = Exception("(401) Unauthorized")

        await search_destination_guides.ainvoke("first call")
        assert mod._initialised is True

        # Second call should not retry build_index
        mock_build.reset_mock()
        await search_destination_guides.ainvoke("second call")
        mock_build.assert_not_called()

    @patch("src.tools.destination_rag.build_index")
    async def test_query_exception_returns_empty_matches(self, mock_build):
        """When index.query raises at runtime, _query_namespace returns []."""
        mock_index = MagicMock()
        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_query.return_value = [0.1] * 3072
        mock_index.query.side_effect = Exception("(401) Unauthorized")
        mock_build.return_value = (mock_index, mock_emb_gen)

        result = await search_destination_guides.ainvoke("test query")

        assert "No relevant destination guide content" in result
