"""Cross-encoder reranker for RAG + web results.

Re-scores candidate chunks using a Cohere Rerank (or Jina) cross-encoder
to surface the most relevant results, regardless of their original source
(Pinecone cosine similarity or Tavily relevance).

Falls back gracefully to the original ordering when the reranker API is
unavailable or the dependency is not installed.
"""

import os
from dataclasses import dataclass

from custom_logging import AppLogger

logger = AppLogger(logger_name="rag.reranker", level="DEBUG")


@dataclass
class RankedResult:
    """A single reranked result with its new relevance score."""

    text: str
    score: float
    metadata: dict
    source: str  # "guide" or "web"


def rerank(
    query: str,
    candidates: list[dict],
    *,
    top_n: int = 5,
    model: str = "rerank-v3.5",
) -> list[RankedResult]:
    """Rerank candidate results using Cohere cross-encoder.

    Args:
        query: The original user query.
        candidates: List of dicts with at least ``text``, ``metadata``,
                    ``source`` keys.  ``score`` is optional (original score).
        top_n: Number of results to return after reranking.
        model: Cohere rerank model name.

    Returns:
        Top-N ``RankedResult`` objects sorted by cross-encoder relevance.
        Falls back to original order (by existing score) if Cohere is unavailable.
    """
    if not candidates:
        return []

    api_key = os.environ.get("COHERE_API_KEY")
    if not api_key:
        logger.warning("COHERE_API_KEY not set — falling back to original ranking")
        return _fallback_ranking(candidates, top_n)

    try:
        import cohere
    except ImportError:
        logger.warning("cohere package not installed — falling back to original ranking")
        return _fallback_ranking(candidates, top_n)

    try:
        client = cohere.ClientV2(api_key=api_key)
        documents = [c["text"] for c in candidates]

        response = client.rerank(
            query=query,
            documents=documents,
            top_n=min(top_n, len(candidates)),
            model=model,
        )

        ranked: list[RankedResult] = []
        for r in response.results:
            original = candidates[r.index]
            ranked.append(
                RankedResult(
                    text=original["text"],
                    score=r.relevance_score,
                    metadata=original.get("metadata", {}),
                    source=original.get("source", "unknown"),
                )
            )

        logger.info(
            f"Reranked {len(candidates)} → {len(ranked)} results "
            f"(top score: {ranked[0].score:.3f})"
        )
        return ranked

    except Exception:
        logger.warning("Cohere rerank failed — falling back to original ranking", exc_info=True)
        return _fallback_ranking(candidates, top_n)


def _fallback_ranking(candidates: list[dict], top_n: int) -> list[RankedResult]:
    """Sort by original score when reranker is unavailable."""
    sorted_candidates = sorted(
        candidates,
        key=lambda c: c.get("score", 0),
        reverse=True,
    )[:top_n]
    return [
        RankedResult(
            text=c["text"],
            score=c.get("score", 0),
            metadata=c.get("metadata", {}),
            source=c.get("source", "unknown"),
        )
        for c in sorted_candidates
    ]
