"""LLM-driven query decomposition for multi-aspect RAG retrieval.

Breaks broad travel queries into focused sub-queries so each one targets
a different section of the knowledge base (Eat, See, Get around, etc.).
Falls back to the original query when decomposition is unnecessary or the
LLM call fails.
"""

import json
import re

from custom_logging import AppLogger
from src.agent.prompts import _DECOMPOSE_PROMPT

logger = AppLogger(logger_name="rag.query_decomposer", level="DEBUG")


async def decompose_query(query: str) -> list[str]:
    """Decompose a broad query into focused sub-queries using the LLM.

    Returns a list of 1-4 sub-queries.  Falls back to ``[query]`` on error.
    """
    # Short / already-focused queries don't need decomposition
    word_count = len(query.split())
    if word_count <= 4:
        logger.debug(
            f"Query too short for decomposition ({word_count} words), skipping"
        )
        return [query]

    try:
        from src.agent.llm import get_llm

        llm = get_llm(tier="utility")
        prompt = _DECOMPOSE_PROMPT.format(query=query)
        response = await llm.ainvoke(prompt)
        # Responses API returns content as a list of blocks, not a string
        raw = response.content
        if isinstance(raw, list):
            content = " ".join(
                b["text"]
                for b in raw
                if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
            ).strip()
        else:
            content = raw.strip()

        # Extract JSON array from response (handle markdown fences)
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if not json_match:
            logger.warning(f"Could not parse decomposition response: {content[:200]}")
            return [query]

        sub_queries = json.loads(json_match.group())

        if not isinstance(sub_queries, list) or not all(
            isinstance(q, str) for q in sub_queries
        ):
            logger.warning(f"Invalid decomposition format: {sub_queries}")
            return [query]

        # Clamp to 1-4 sub-queries
        sub_queries = sub_queries[:4]
        if not sub_queries:
            return [query]

        logger.info(f"Decomposed '{query[:60]}' → {len(sub_queries)} sub-queries")
        return sub_queries

    except Exception:
        logger.warning(
            "Query decomposition failed — using original query", exc_info=True
        )
        return [query]


def merge_results(result_sets: list[list[dict]]) -> list[dict]:
    """Merge and deduplicate results from multiple sub-query retrievals.

    Deduplicates by text content hash, keeping the highest-scored version.
    """
    seen: dict[str, dict] = {}
    for results in result_sets:
        for r in results:
            text = r.get("text", "")
            key = text[:200]  # Use first 200 chars as identity key
            existing = seen.get(key)
            if existing is None or r.get("score", 0) > existing.get("score", 0):
                seen[key] = r
    merged = sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)
    logger.debug(
        f"Merged {sum(len(rs) for rs in result_sets)} → {len(merged)} unique results"
    )
    return merged
