"""Tests for src/tools/destination_rag.py — RAG search tool (Pinecone backend)."""

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


class TestSearchDestinationGuides:
    @patch("src.tools.destination_rag.build_index")
    def test_returns_relevant_content(self, mock_build):
        mock_index = MagicMock()
        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_query.return_value = [0.1] * 3072
        mock_index.query.return_value = _make_pinecone_response(
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
            ]
        )
        mock_build.return_value = (mock_index, mock_emb_gen)

        result = search_destination_guides.invoke("Kyoto temple tips")

        assert "Fushimi Inari" in result
        assert "conveyor-belt sushi" in result
        assert "japan_guide.md" in result
        assert "Guide confidence: high" in result
        mock_emb_gen.embed_query.assert_called_once_with("Kyoto temple tips")
        mock_index.query.assert_called_once()

    @patch("src.tools.destination_rag.build_index")
    def test_returns_message_when_no_guides(self, mock_build):
        mock_build.return_value = None

        result = search_destination_guides.invoke("anything")

        assert "No destination guides" in result

    @patch("src.tools.destination_rag.build_index")
    def test_returns_message_when_no_results(self, mock_build):
        mock_index = MagicMock()
        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_query.return_value = [0.1] * 3072
        mock_index.query.return_value = _make_pinecone_response([])
        mock_build.return_value = (mock_index, mock_emb_gen)

        result = search_destination_guides.invoke("alien planet travel")

        assert "No relevant destination guide content" in result
        assert "search_web" in result or "search_hidden_gems" in result

    @patch("src.tools.destination_rag.build_index")
    def test_formats_multiple_sources(self, mock_build):
        mock_index = MagicMock()
        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_query.return_value = [0.1] * 3072
        mock_index.query.return_value = _make_pinecone_response(
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
            ]
        )
        mock_build.return_value = (mock_index, mock_emb_gen)

        result = search_destination_guides.invoke("city tips")

        # Both sources should appear, separated by ---
        assert "japan_guide.md" in result
        assert "france_guide.md" in result
        assert "---" in result

    @patch("src.tools.destination_rag.build_index")
    def test_includes_section_in_output(self, mock_build):
        """Output should include the section metadata."""
        mock_index = MagicMock()
        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_query.return_value = [0.1] * 3072
        mock_index.query.return_value = _make_pinecone_response(
            [
                {
                    "metadata": {
                        "source": "japan_guide.md",
                        "text": "Sushi tips",
                        "section": "Eat",
                    },
                    "score": 0.90,
                },
            ]
        )
        mock_build.return_value = (mock_index, mock_emb_gen)

        result = search_destination_guides.invoke("food tips")
        assert "section: Eat" in result

    @patch("src.tools.destination_rag.build_index")
    def test_lazy_init_calls_build_once(self, mock_build):
        mock_index = MagicMock()
        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_query.return_value = [0.1] * 3072
        mock_index.query.return_value = _make_pinecone_response(
            [
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Test",
                        "section": "intro",
                    },
                    "score": 0.80,
                },
            ]
        )
        mock_build.return_value = (mock_index, mock_emb_gen)

        search_destination_guides.invoke("query 1")
        search_destination_guides.invoke("query 2")

        # build_index should only be called once (lazy init)
        mock_build.assert_called_once()

    @patch("src.tools.destination_rag.build_index")
    def test_filters_low_relevance_matches(self, mock_build):
        """Matches below _MIN_RELEVANCE (0.40) should be excluded."""
        mock_index = MagicMock()
        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_query.return_value = [0.1] * 3072
        mock_index.query.return_value = _make_pinecone_response(
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
            ]
        )
        mock_build.return_value = (mock_index, mock_emb_gen)

        result = search_destination_guides.invoke("test query")

        assert "Good match" in result
        assert "Noisy match" not in result

    @patch("src.tools.destination_rag.build_index")
    def test_low_confidence_includes_web_nudge(self, mock_build):
        """Low-confidence results should nudge agent to use web search."""
        mock_index = MagicMock()
        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_query.return_value = [0.1] * 3072
        mock_index.query.return_value = _make_pinecone_response(
            [
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Weak match",
                        "section": "See",
                    },
                    "score": 0.48,
                },
            ]
        )
        mock_build.return_value = (mock_index, mock_emb_gen)

        result = search_destination_guides.invoke("obscure topic")

        assert "Guide confidence: low" in result
        assert "search_web" in result

    @patch("src.tools.destination_rag.build_index")
    def test_medium_confidence_includes_complement_hint(self, mock_build):
        """Medium-confidence results should suggest complementing with web search."""
        mock_index = MagicMock()
        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_query.return_value = [0.1] * 3072
        mock_index.query.return_value = _make_pinecone_response(
            [
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Decent match",
                        "section": "See",
                    },
                    "score": 0.60,
                },
            ]
        )
        mock_build.return_value = (mock_index, mock_emb_gen)

        result = search_destination_guides.invoke("moderate topic")

        assert "Guide confidence: medium" in result
        assert "search_web" in result

    @patch("src.tools.destination_rag.build_index")
    def test_top_k_parameter(self, mock_build):
        """Custom top_k should be passed to Pinecone query."""
        mock_index = MagicMock()
        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_query.return_value = [0.1] * 3072
        mock_index.query.return_value = _make_pinecone_response(
            [
                {
                    "metadata": {
                        "source": "test.md",
                        "text": "Result",
                        "section": "See",
                    },
                    "score": 0.80,
                },
            ]
        )
        mock_build.return_value = (mock_index, mock_emb_gen)

        search_destination_guides.invoke({"query": "test", "top_k": 8})

        call_kwargs = mock_index.query.call_args
        assert call_kwargs.kwargs.get("top_k") == 8 or call_kwargs[1].get("top_k") == 8
