"""RAG-powered destination guide search tool (Pinecone backend)."""

from typing import Optional

from langchain_core.tools import tool

from custom_logging import AppLogger
from src.rag.indexer import NAMESPACE, build_index

logger = AppLogger(logger_name="tools.rag", level="DEBUG")

# Lazy-initialised Pinecone index + embedding generator (built once on first call)
_index = None
_emb_gen = None
_initialised = False


def _get_index_and_embeddings():
    global _index, _emb_gen, _initialised
    if not _initialised:
        result = build_index()
        if result is not None:
            _index, _emb_gen = result
        _initialised = True
    return _index, _emb_gen


@tool
def search_destination_guides(
    query: str,
    destinations: Optional[list[str]] = None,
) -> str:
    """Search curated destination guides for local tips, cultural context,
    neighborhood recommendations, and insider travel knowledge.

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
    """
    index, emb_gen = _get_index_and_embeddings()
    if index is None or emb_gen is None:
        return "No destination guides are currently indexed."

    # Embed the query and search Pinecone
    logger.debug(f"RAG query: {query!r}, destinations filter: {destinations!r}")
    query_vector = emb_gen.embed_query(query)

    query_kwargs: dict = {
        "vector": query_vector,
        "top_k": 4,
        "include_metadata": True,
        "namespace": NAMESPACE,
    }
    # Scope search to confirmed destinations when available
    if destinations:
        slugs = [d.lower().replace(" ", "_") for d in destinations]
        query_kwargs["filter"] = {"destination": {"$in": slugs}}

    results = index.query(**query_kwargs)

    matches = results.get("matches", [])
    match_summary = [
        (m["metadata"].get("source", "?"), f"{m.get('score', 0):.2f}")
        for m in matches
    ]
    logger.info(f"RAG '{query[:60]}' → {len(matches)} match(es) {match_summary}")

    if not matches:
        return "No relevant destination guide content found for this query."

    sections: list[str] = []
    for i, match in enumerate(matches, 1):
        source = match["metadata"].get("source", "unknown")
        text = match["metadata"].get("text", "")
        score = match.get("score", 0)
        section = match["metadata"].get("section", "")
        sections.append(
            f"[{i}] (Source: {source}, section: {section}, relevance: {score:.2f})\n{text}"
        )

    return "\n\n---\n\n".join(sections)
