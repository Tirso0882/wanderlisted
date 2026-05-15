"""Tests for src/rag/reranker.py — cross-encoder reranking with graceful fallback."""

from unittest.mock import MagicMock, patch


from src.rag.reranker import RankedResult, _fallback_ranking, rerank


_CANDIDATES = [
    {"text": "Visit temples in Kyoto", "score": 0.65, "metadata": {"section": "See"}, "source": "guide"},
    {"text": "Try ramen in Tokyo", "score": 0.72, "metadata": {"section": "Eat"}, "source": "guide"},
    {"text": "Take the JR Pass", "score": 0.60, "metadata": {"section": "Get around"}, "source": "web"},
]


class TestFallbackRanking:
    def test_sorts_by_original_score(self):
        ranked = _fallback_ranking(_CANDIDATES, top_n=3)
        assert ranked[0].text == "Try ramen in Tokyo"
        assert ranked[1].text == "Visit temples in Kyoto"
        assert ranked[2].text == "Take the JR Pass"

    def test_respects_top_n(self):
        ranked = _fallback_ranking(_CANDIDATES, top_n=1)
        assert len(ranked) == 1
        assert ranked[0].text == "Try ramen in Tokyo"

    def test_returns_ranked_result_objects(self):
        ranked = _fallback_ranking(_CANDIDATES, top_n=2)
        assert all(isinstance(r, RankedResult) for r in ranked)
        assert ranked[0].source == "guide"

    def test_empty_candidates(self):
        assert _fallback_ranking([], top_n=5) == []


class TestRerank:
    def test_empty_candidates_returns_empty(self):
        assert rerank("test query", []) == []

    def test_no_api_key_falls_back(self, monkeypatch):
        """Without COHERE_API_KEY, should use fallback ranking."""
        monkeypatch.delenv("COHERE_API_KEY", raising=False)
        ranked = rerank("Tokyo food", _CANDIDATES)

        assert len(ranked) <= len(_CANDIDATES)
        # Fallback sorts by original score
        assert ranked[0].text == "Try ramen in Tokyo"

    @patch.dict("os.environ", {"COHERE_API_KEY": "test-key"})
    def test_import_error_falls_back(self):
        """When cohere is not installed, should fallback gracefully."""
        with patch.dict("sys.modules", {"cohere": None}):
            ranked = rerank("Tokyo food", _CANDIDATES)
            # Should still return results (via fallback)
            assert len(ranked) > 0

    @patch.dict("os.environ", {"COHERE_API_KEY": "test-key"})
    def test_cohere_success(self):
        """Successful Cohere reranking should return reordered results."""
        mock_response = MagicMock()
        mock_result_0 = MagicMock()
        mock_result_0.index = 2  # JR Pass (originally 3rd)
        mock_result_0.relevance_score = 0.95
        mock_result_1 = MagicMock()
        mock_result_1.index = 0  # Temples (originally 1st)
        mock_result_1.relevance_score = 0.80
        mock_response.results = [mock_result_0, mock_result_1]

        mock_client = MagicMock()
        mock_client.rerank.return_value = mock_response

        mock_cohere = MagicMock()
        mock_cohere.ClientV2.return_value = mock_client

        with patch.dict("sys.modules", {"cohere": mock_cohere}):
            ranked = rerank("Tokyo transport", _CANDIDATES, top_n=2)

        assert len(ranked) == 2
        assert ranked[0].text == "Take the JR Pass"
        assert ranked[0].score == 0.95
        assert ranked[1].text == "Visit temples in Kyoto"

    @patch.dict("os.environ", {"COHERE_API_KEY": "test-key"})
    def test_cohere_api_error_falls_back(self):
        """Cohere API error should fallback gracefully."""
        mock_cohere = MagicMock()
        mock_cohere.ClientV2.return_value.rerank.side_effect = RuntimeError("API down")

        with patch.dict("sys.modules", {"cohere": mock_cohere}):
            ranked = rerank("Tokyo query", _CANDIDATES)

        # Should still return results via fallback
        assert len(ranked) > 0
        assert ranked[0].text == "Try ramen in Tokyo"  # Highest original score
