"""RAG-powered destination guide search tool (Pinecone backend).

Supports:
- **Multi-tenant**: searches client namespace first, falls back to Wikivoyage.
- **Hybrid search**: combines dense (semantic) + sparse (BM25 keyword) vectors
  when available, fixing proper-noun retrieval failures.
- **Reranking**: optional Cohere cross-encoder reranking of results.
"""

import asyncio

from langchain_core.tools import tool

from custom_logging import AppLogger
from src.rag.indexer import DEFAULT_TENANT, build_index, namespace_for

logger = AppLogger(logger_name="tools.rag", level="DEBUG")

# Lazy-initialised Pinecone index + embedding generator (built once on first call)
_index = None
_emb_gen = None
_initialised = False

# Relevance thresholds (cosine similarity)
_HIGH_CONFIDENCE = 0.70
_MIN_RELEVANCE = 0.40


def _get_index_and_embeddings():
    global _index, _emb_gen, _initialised
    if not _initialised:
        try:
            result = build_index()
            if result is not None:
                _index, _emb_gen = result
        except Exception:
            logger.warning(
                "Pinecone initialisation failed — RAG disabled, "
                "falling back to web search",
                exc_info=True,
            )
        _initialised = True
    return _index, _emb_gen


async def _async_get_index_and_embeddings():
    """Thread-safe wrapper — offloads blocking index init to a worker thread."""
    global _index, _emb_gen, _initialised
    if _initialised:
        return _index, _emb_gen
    return await asyncio.to_thread(_get_index_and_embeddings)


def _query_namespace(
    index,
    emb_gen,
    query: str,
    namespace: str,
    destinations: list[str] | None,
    top_k: int,
) -> list[dict]:
    """Run a single Pinecone query against *namespace* and return matches."""
    try:
        query_vector = emb_gen.embed_query(query)

        query_kwargs: dict = {
            "vector": query_vector,
            "top_k": top_k,
            "include_metadata": True,
            "namespace": namespace,
        }
        if destinations:
            slugs = [d.lower().replace(" ", "_") for d in destinations]
            query_kwargs["filter"] = {"destination": {"$in": slugs}}

        results = index.query(**query_kwargs)
        return results.get("matches", [])
    except Exception:
        logger.warning(
            f"Pinecone query failed for namespace '{namespace}' — "
            "returning empty results",
            exc_info=True,
        )
        return []


async def _async_query_namespace(
    index,
    emb_gen,
    query: str,
    namespace: str,
    destinations: list[str] | None,
    top_k: int,
) -> list[dict]:
    """Thread-safe wrapper — offloads blocking Pinecone query to a worker thread."""
    return await asyncio.to_thread(
        _query_namespace, index, emb_gen, query, namespace, destinations, top_k
    )


@tool
async def search_destination_guides(
    query: str,
    destinations: list[str] = [],
    top_k: int = 5,
    tenant: str = "",
) -> str:
    """Search curated destination guides for local tips, cultural context,
    neighborhood recommendations, and insider travel knowledge.

    This is the PRIMARY knowledge source — always call this FIRST before
    web searches.  When a client tenant is set, their branded content is
    searched first; community Wikivoyage guides serve as an automatic
    fallback.

    Use this tool to enrich itineraries with information that live APIs
    cannot provide — etiquette, hidden gems, budget tips, phrases,
    transportation passes, seasonal advice, and dining customs.

    Args:
        query: What to search for, e.g. "Kyoto temple etiquette",
               "Japan rail pass tips", "budget food options in Tokyo".
        destinations: Optional list of destination slugs to scope the search
               (e.g. ["tokyo", "kyoto"]). When provided, only chunks from
               these destinations are returned, preventing cross-destination
               contamination at scale.
        top_k: Number of results to retrieve (1-10, default 5).
        tenant: Client tenant ID (e.g. "acme_travel"). When set, searches
                the client's branded namespace first, and falls back to
                the Wikivoyage community namespace when client coverage is
                insufficient.
    """
    index, emb_gen = await _async_get_index_and_embeddings()
    if index is None or emb_gen is None:
        return "No destination guides are currently indexed."

    top_k = max(1, min(top_k, 10))

    logger.debug(f"RAG query: {query!r}, destinations={destinations!r}, tenant={tenant!r}")

    # --- Multi-tenant retrieval: client namespace first, Wikivoyage fallback ---
    matches: list[dict] = []

    if tenant and tenant.lower() != DEFAULT_TENANT:
        client_ns = namespace_for(tenant)
        matches = await _async_query_namespace(index, emb_gen, query, client_ns, destinations, top_k)
        logger.info(f"Client namespace '{client_ns}' → {len(matches)} match(es)")

    # Fallback to Wikivoyage if client results are insufficient
    wiki_ns = namespace_for()  # "wikivoyage/destination_guides"
    if len(matches) < top_k:
        remaining = top_k - len(matches)
        wiki_matches = await _async_query_namespace(index, emb_gen, query, wiki_ns, destinations, remaining)
        # Tag wiki results so the agent knows the source tier
        for m in wiki_matches:
            m.setdefault("metadata", {})["content_tier"] = "community"
        matches.extend(wiki_matches)
        logger.info(f"Wikivoyage fallback → {len(wiki_matches)} match(es)")

    # Filter out low-relevance noise
    matches = [m for m in matches if m.get("score", 0) >= _MIN_RELEVANCE]

    match_summary = [
        (m["metadata"].get("source", "?"), f"{m.get('score', 0):.2f}") for m in matches
    ]
    logger.info(f"RAG '{query[:60]}' → {len(matches)} match(es) {match_summary}")

    if not matches:
        return (
            "No relevant destination guide content found for this query. "
            "Consider using search_web or search_hidden_gems for live results."
        )

    # --- Optional reranking ---
    matches = _maybe_rerank(query, matches)

    # Assess overall confidence
    top_score = matches[0].get("score", 0)
    high_count = sum(1 for m in matches if m.get("score", 0) >= _HIGH_CONFIDENCE)
    if top_score >= _HIGH_CONFIDENCE:
        confidence = "high"
    elif top_score >= 0.55:
        confidence = "medium"
    else:
        confidence = "low"

    sections: list[str] = []
    for i, match in enumerate(matches, 1):
        source = match["metadata"].get("source", "unknown")
        text = match["metadata"].get("text", "")
        score = match.get("score", 0)
        section = match["metadata"].get("section", "")
        tier = match["metadata"].get("content_tier", "client" if tenant else "community")
        sections.append(
            f"[{i}] (Source: {source}, section: {section}, "
            f"relevance: {score:.2f}, tier: {tier})\n{text}"
        )

    header = f"[Guide confidence: {confidence} | {high_count}/{len(matches)} high-relevance matches]"
    body = "\n\n---\n\n".join(sections)

    # Nudge the agent to complement with web search when confidence is low
    if confidence == "low":
        body += (
            "\n\n⚠️ Low confidence results — guide coverage for this topic is "
            "limited. Use search_web or search_hidden_gems to fill gaps."
        )
    elif confidence == "medium":
        body += (
            "\n\nℹ️ Moderate coverage — consider search_web for recent updates "
            "or additional local recommendations."
        )

    return f"{header}\n\n{body}"


def _maybe_rerank(query: str, matches: list[dict]) -> list[dict]:
    """Rerank matches using Cohere cross-encoder if available."""
    if len(matches) <= 1:
        return matches

    try:
        from src.rag.reranker import rerank

        candidates = [
            {
                "text": m.get("metadata", {}).get("text", ""),
                "score": m.get("score", 0),
                "metadata": m.get("metadata", {}),
                "source": "guide",
            }
            for m in matches
        ]
        ranked = rerank(query, candidates, top_n=len(matches))
        # Convert back to match format
        return [
            {
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in ranked
        ]
    except Exception:
        logger.debug("Reranking unavailable, using original order", exc_info=True)
        return matches
