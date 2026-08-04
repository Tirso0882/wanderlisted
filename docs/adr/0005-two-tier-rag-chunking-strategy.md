# 0005 — Two-tier (section-level + recursive) RAG chunking

**Status:** Superseded by [0006](0006-tavily-only-destination-pipeline.md) · **Date:** 2026-07-10 (retroactively documented) · **Deciders:** Tirso Gomez

## Context

The RAG knowledge base is built from **Wikivoyage-style destination guides**, which have a consistent set of
**bare-text section headings** (`Understand`, `Get in`, `Get around`, `See`, `Do`, `Eat`, `Sleep`, `Stay
safe`, …). Chunk quality drives retrieval quality, and two naive approaches failed:

- **Fixed-size character chunking** splits mid-section, cutting a hotel list or a "Get around" explanation in
  half and destroying the semantic boundary the author intended.
- **`SemanticChunker`** (langchain-experimental, used in an earlier iteration) was slow, added embedding cost
  at index time, and produced inconsistent boundaries. It was removed (see repo memory
  `rag-refactor-architecture`).

The system also needs to stay **future-proof** for documents that *don't* have Wikivoyage headings (e.g. PDFs
a client brings), and needs lightweight metadata for Pinecone filtering by destination and topic.

## Decision

Implement a **two-tier strategy** in [../../src/rag/chunker.py](../../src/rag/chunker.py):

1. **Section-level (primary):** detect known Wikivoyage headings with a compiled regex, split on them,
   **sub-split oversized** sections (via `RecursiveCharacterTextSplitter`, ~2000 chars / 200 overlap) and
   **merge tiny** ones. This preserves author-intended semantic boundaries.
2. **Recursive character (fallback):** for documents with no recognizable headings, fall back to
   `RecursiveCharacterTextSplitter` alone.

Every chunk is enriched with metadata — `destination`, `section`, `chunk_position`, `content_type`
(keyword-classified into topics like `food_and_drink`, `accommodation`) — so retrieval can filter in Pinecone
before reranking.

## Consequences

**Positive**

- Chunks align with semantic sections → higher retrieval precision and cleaner reranking inputs.
- Metadata enables cheap pre-filtering (by destination/section) before the Cohere rerank stage.
- Graceful generalization: unknown document shapes still index via the recursive fallback.

**Negative / costs**

- The section list is **domain-specific** (Wikivoyage). Arbitrary corpora get only the recursive path until a
  loader/normalizer is added (tracked as the document-processing pipeline in the roadmap).
- `content_type` classification is **keyword-based** and therefore approximate.
- Sub-split/merge thresholds are heuristics that may need tuning for very long or very terse guides.

## Alternatives considered

| Alternative | Why rejected | When to choose it instead |
|-------------|--------------|---------------------------|
| **Fixed-size recursive only** | Ignores section boundaries; worse retrieval | Homogeneous prose with no structure |
| **`SemanticChunker`** | Slow, extra embedding cost, inconsistent — removed in refactor | When documents lack any structural signal and quality justifies the cost |
| **LLM-based chunking** | Expensive and slow at index time for a large corpus | Small, high-value corpora where index cost is negligible |

## References

- Code: [../../src/rag/chunker.py](../../src/rag/chunker.py) (`SECTION_NAMES`, two-tier logic, metadata enrichment)
- Code: [../../src/rag/indexer.py](../../src/rag/indexer.py) (chunk → embed → Pinecone upsert)
- Repo memory: `rag-refactor-architecture`
- Rationale doc: [../architecture/CHUNKING_STRATEGY_RATIONALE.md](../architecture/CHUNKING_STRATEGY_RATIONALE.md)
