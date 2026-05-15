"""Tests for src/rag/query_decomposer.py — LLM-driven query decomposition."""

from unittest.mock import AsyncMock, MagicMock, patch


from src.rag.query_decomposer import decompose_query, merge_results


class TestDecomposeQuery:
    async def test_short_query_skips_decomposition(self):
        """Queries with ≤4 words should be returned as-is."""
        result = await decompose_query("Tokyo food")
        assert result == ["Tokyo food"]

    async def test_short_single_word(self):
        result = await decompose_query("ramen")
        assert result == ["ramen"]

    @patch("src.agent.llm.get_llm")
    async def test_successful_decomposition(self, mock_get_model):
        """Broad query should be decomposed into sub-queries."""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = (
            '["Tokyo local food", "Tokyo public transport", "Tokyo temples"]'
        )
        mock_llm.ainvoke.return_value = mock_response
        mock_get_model.return_value = mock_llm

        result = await decompose_query("plan my trip to Tokyo with everything")

        assert len(result) == 3
        assert "Tokyo local food" in result
        assert "Tokyo public transport" in result

    @patch("src.agent.llm.get_llm")
    async def test_decomposition_with_markdown_fences(self, mock_get_model):
        """LLM sometimes wraps response in markdown code fences."""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '```json\n["Paris food", "Paris sightseeing"]\n```'
        mock_llm.ainvoke.return_value = mock_response
        mock_get_model.return_value = mock_llm

        result = await decompose_query("plan a trip to Paris with food and sights")

        assert len(result) == 2

    @patch("src.agent.llm.get_llm")
    async def test_decomposition_clamped_to_4(self, mock_get_model):
        """Even if LLM returns >4 sub-queries, we cap at 4."""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '["a", "b", "c", "d", "e", "f"]'
        mock_llm.ainvoke.return_value = mock_response
        mock_get_model.return_value = mock_llm

        result = await decompose_query("plan everything possible for my long trip")

        assert len(result) == 4

    @patch("src.agent.llm.get_llm")
    async def test_decomposition_invalid_json_falls_back(self, mock_get_model):
        """If LLM returns non-JSON, fall back to original query."""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "I think you should search for Tokyo food."
        mock_llm.ainvoke.return_value = mock_response
        mock_get_model.return_value = mock_llm

        query = "plan my trip to Tokyo with lots of details"
        result = await decompose_query(query)

        assert result == [query]

    @patch("src.agent.llm.get_llm")
    async def test_decomposition_llm_error_falls_back(self, mock_get_model):
        """If LLM call fails, fall back to original query."""
        mock_get_model.side_effect = RuntimeError("LLM unavailable")

        query = "plan my trip to Tokyo with lots of details"
        result = await decompose_query(query)

        assert result == [query]


class TestMergeResults:
    def test_deduplicates_by_text(self):
        """Same text appearing in multiple result sets should be merged."""
        set_a = [
            {
                "text": "Tokyo temples are beautiful",
                "score": 0.70,
                "metadata": {"section": "See"},
            },
            {
                "text": "Try ramen in Shinjuku",
                "score": 0.65,
                "metadata": {"section": "Eat"},
            },
        ]
        set_b = [
            {
                "text": "Tokyo temples are beautiful",
                "score": 0.75,
                "metadata": {"section": "See"},
            },
            {
                "text": "Take the JR Pass for trains",
                "score": 0.60,
                "metadata": {"section": "Get around"},
            },
        ]

        merged = merge_results([set_a, set_b])

        # Should keep highest score for duplicate
        texts = [r["text"] for r in merged]
        assert texts.count("Tokyo temples are beautiful") == 1
        temple_result = next(r for r in merged if "temples" in r["text"])
        assert temple_result["score"] == 0.75  # Kept the higher score

    def test_sorted_by_score_descending(self):
        set_a = [{"text": "Low", "score": 0.40}]
        set_b = [{"text": "High", "score": 0.90}]

        merged = merge_results([set_a, set_b])
        assert merged[0]["text"] == "High"

    def test_empty_input(self):
        assert merge_results([]) == []
        assert merge_results([[], []]) == []

    def test_single_set(self):
        results = [{"text": "Only result", "score": 0.80}]
        merged = merge_results([results])
        assert len(merged) == 1
