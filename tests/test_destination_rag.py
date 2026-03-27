"""Tests for src/tools/destination_rag.py — RAG search tool (Pinecone backend)."""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.destination_rag import search_destination_guides


# Reset the lazy-init state before each test
@pytest.fixture(autouse=True)
def _reset_index():
    import src.tools.destination_rag as mod
    mod._index = None
    mod._embeddings = None
    mod._initialised = False
    yield
    mod._index = None
    mod._embeddings = None
    mod._initialised = False


def _make_pinecone_response(matches):
    """Build a Pinecone-style query response dict."""
    return {"matches": matches}


class TestSearchDestinationGuides:
    @patch("src.tools.destination_rag.build_index")
    def test_returns_relevant_content(self, mock_build):
        mock_index = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 1536
        mock_index.query.return_value = _make_pinecone_response([
            {"metadata": {"source": "japan_guide.md", "text": "Visit Fushimi Inari early morning to avoid crowds."}, "score": 0.92},
            {"metadata": {"source": "japan_guide.md", "text": "Try conveyor-belt sushi for affordable options."}, "score": 0.87},
        ])
        mock_build.return_value = (mock_index, mock_embeddings)

        result = search_destination_guides.invoke("Kyoto temple tips")

        assert "Fushimi Inari" in result
        assert "conveyor-belt sushi" in result
        assert "japan_guide.md" in result
        mock_embeddings.embed_query.assert_called_once_with("Kyoto temple tips")
        mock_index.query.assert_called_once()

    @patch("src.tools.destination_rag.build_index")
    def test_returns_message_when_no_guides(self, mock_build):
        mock_build.return_value = None

        result = search_destination_guides.invoke("anything")

        assert "No destination guides" in result

    @patch("src.tools.destination_rag.build_index")
    def test_returns_message_when_no_results(self, mock_build):
        mock_index = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 1536
        mock_index.query.return_value = _make_pinecone_response([])
        mock_build.return_value = (mock_index, mock_embeddings)

        result = search_destination_guides.invoke("alien planet travel")

        assert "No relevant destination guide content" in result

    @patch("src.tools.destination_rag.build_index")
    def test_formats_multiple_sources(self, mock_build):
        mock_index = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 1536
        mock_index.query.return_value = _make_pinecone_response([
            {"metadata": {"source": "japan_guide.md", "text": "Tokyo info"}, "score": 0.90},
            {"metadata": {"source": "france_guide.md", "text": "Paris info"}, "score": 0.85},
        ])
        mock_build.return_value = (mock_index, mock_embeddings)

        result = search_destination_guides.invoke("city tips")

        # Both sources should appear, separated by ---
        assert "japan_guide.md" in result
        assert "france_guide.md" in result
        assert "---" in result

    @patch("src.tools.destination_rag.build_index")
    def test_lazy_init_calls_build_once(self, mock_build):
        mock_index = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 1536
        mock_index.query.return_value = _make_pinecone_response([
            {"metadata": {"source": "test.md", "text": "Test"}, "score": 0.80},
        ])
        mock_build.return_value = (mock_index, mock_embeddings)

        search_destination_guides.invoke("query 1")
        search_destination_guides.invoke("query 2")

        # build_index should only be called once (lazy init)
        mock_build.assert_called_once()
