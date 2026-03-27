"""RAG-powered destination guide search tool (Pinecone backend)."""

import logging

from langchain_core.tools import tool

from src.rag.indexer import NAMESPACE, build_index

logger = logging.getLogger(__name__)

# Lazy-initialised Pinecone index + embeddings (built once on first call)
_index = None
_embeddings = None
_initialised = False


def _get_index_and_embeddings():
    global _index, _embeddings, _initialised
    if not _initialised:
        result = build_index()
        if result is not None:
            _index, _embeddings = result
        _initialised = True
    return _index, _embeddings


@tool
def search_destination_guides(query: str) -> str:
    """Search curated destination guides for local tips, cultural context,
    neighborhood recommendations, and insider travel knowledge.

    Use this tool to enrich itineraries with information that live APIs
    cannot provide — etiquette, hidden gems, budget tips, phrases,
    transportation passes, seasonal advice, and dining customs.

    Args:
        query: What to search for, e.g. "Kyoto temple etiquette",
               "Japan rail pass tips", "budget food options in Tokyo".
    """
    index, embeddings = _get_index_and_embeddings()
    if index is None or embeddings is None:
        return "No destination guides are currently indexed."

    # Embed the query and search Pinecone
    logger.debug("RAG query: %r", query)
    query_vector = embeddings.embed_query(query)
    results = index.query(
        vector=query_vector,
        top_k=4,
        include_metadata=True,
        namespace=NAMESPACE,
    )

    matches = results.get("matches", [])
    logger.info("RAG '%s' → %d match(es) %s",
        query[:60],
        len(matches),
        [(m["metadata"].get("source", "?"), f"{m.get('score', 0):.2f}") for m in matches],
    )

    if not matches:
        return "No relevant destination guide content found for this query."

    sections: list[str] = []
    for i, match in enumerate(matches, 1):
        source = match["metadata"].get("source", "unknown")
        text = match["metadata"].get("text", "")
        score = match.get("score", 0)
        sections.append(f"[{i}] (Source: {source}, relevance: {score:.2f})\n{text}")

    return "\n\n---\n\n".join(sections)
