"""Composite destination research tool — guaranteed RAG + web fallback.

Orchestrates search_destination_guides and Tavily in code so the fallback
to web search is a **code-level guarantee**, not a prompt suggestion.
Includes a TTL cache for Tavily results to control API costs.
"""

import asyncio
import hashlib
import time
from typing import Optional

from langchain_core.tools import tool

from custom_logging import AppLogger
from src.tools.destination_rag import (
    _HIGH_CONFIDENCE,
    search_destination_guides,
)
from src.tools.web_search import _tavily_search

logger = AppLogger(logger_name="tools.research", level="DEBUG")

# ---------------------------------------------------------------------------
#  TTL cache for Tavily results
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 3600 * 6  # 6 hours — web results stay relevant for a while
_CACHE_MAX_SIZE = 200


def _cache_key(query: str) -> str:
    """Deterministic cache key from a query string."""
    return hashlib.sha256(query.encode()).hexdigest()[:16]


def _get_cached(query: str) -> str | None:
    """Return cached result if still fresh, else None."""
    key = _cache_key(query)
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, result = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    logger.debug(f"Cache hit for: {query[:60]!r}")
    return result


def _set_cached(query: str, result: str) -> None:
    """Store result in cache, evicting oldest if full."""
    if len(_cache) >= _CACHE_MAX_SIZE:
        oldest_key = min(_cache, key=lambda k: _cache[k][0])
        del _cache[oldest_key]
    _cache[_cache_key(query)] = (time.monotonic(), result)


async def _cached_tavily_search(query: str, max_results: int = 5) -> str:
    """Tavily search with TTL caching. Returns formatted string."""
    cached = _get_cached(query)
    if cached is not None:
        return cached

    data = await _tavily_search(
        query,
        max_results=max_results,
        search_depth="advanced",
        exclude_domains=["tripadvisor.com"],
    )

    answer = data.get("answer", "")
    results = data.get("results", [])

    if not results and not answer:
        return ""

    sections: list[str] = []
    if answer:
        sections.append(f"**Web summary:** {answer}")

    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        content = r.get("content", "")
        if len(content) > 500:
            content = content[:497] + "..."
        sections.append(
            f"[W{i}] {title}\n"
            f"     Source: {url}\n"
            f"     {content}"
        )

    formatted = "\n\n".join(sections)
    _set_cached(query, formatted)
    return formatted


# ---------------------------------------------------------------------------
#  Composite research tool
# ---------------------------------------------------------------------------

@tool
async def research_destination(
    query: str,
    destinations: Optional[list[str]] = None,
) -> str:
    """Research a destination by combining curated guides AND live web search.

    This is the MAIN tool for destination research. It orchestrates:
    1. Curated guide search (Pinecone RAG) — always runs first
    2. Live web search (Tavily) — runs automatically when:
       - RAG returns no results (destination not in knowledge base)
       - RAG confidence is low or medium
       - Always runs to complement with current info

    Results are labeled by source so you can assess reliability:
    - [1], [2]... = curated guide results (high reliability)
    - [W1], [W2]... = web results (current but less curated)

    Args:
        query: What to research, e.g. "Tokyo cultural etiquette",
               "best street food in Bangkok", "Marrakech hidden gems".
        destinations: Optional list of destination names to scope the
                      guide search (e.g. ["tokyo", "kyoto"]).
    """
    # --- Layer 1: RAG (always runs) ---
    rag_result = search_destination_guides.invoke({
        "query": query,
        "destinations": destinations,
        "top_k": 5,
    })

    # Parse confidence from the RAG result header
    rag_has_results = "Guide confidence:" in rag_result
    rag_confidence = "none"
    if rag_has_results:
        if "confidence: high" in rag_result:
            rag_confidence = "high"
        elif "confidence: medium" in rag_result:
            rag_confidence = "medium"
        else:
            rag_confidence = "low"

    # --- Layer 2: Web search (conditional) ---
    need_web = rag_confidence != "high"

    web_result = ""
    if need_web:
        # Build a destination-enriched query for Tavily
        web_query = query
        if destinations:
            missing = [
                d for d in destinations if d.lower() not in query.lower()
            ]
            if missing:
                web_query = f"{query} {' '.join(missing)}"

        try:
            web_result = await _cached_tavily_search(web_query, max_results=4)
        except Exception:
            logger.warning(f"Tavily search failed for: {web_query!r}", exc_info=True)
            web_result = ""

    # --- Merge results ---
    parts: list[str] = []

    if rag_has_results:
        parts.append("## Curated Guide Results\n")
        parts.append(rag_result)

    if web_result:
        parts.append("\n\n## Live Web Results\n")
        parts.append(web_result)

    if not rag_has_results and not web_result:
        return (
            f"No information found for this query. Neither curated guides nor "
            f"web search returned results for: {query!r}"
        )

    # Summary header
    sources = []
    if rag_has_results:
        sources.append(f"guides ({rag_confidence})")
    if web_result:
        sources.append("web")
    header = f"[Sources: {' + '.join(sources)}]"

    return f"{header}\n\n" + "\n".join(parts)
