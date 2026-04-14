"""RAG chunking strategy evaluator.

Compares five chunking strategies on the same query set and reports:
  - Retrieval scores (cosine similarity)
  - Chunk size distribution (avg / min / max)
  - Hits@1 and Hits@3 (is the right source in top results?)
  - Noise rate (chunks with score < 0.4 in top-3)

Usage:
    python scripts/eval_rag.py            # run all 5 strategies
    python scripts/eval_rag.py --no-cache # ignore cached embeddings

Notes:
- Requires Azure OpenAI embeddings (AZURE_OPENAI_* env vars).
- Does NOT write anything to Pinecone — runs fully locally.

Embeddings are cached in scripts/.eval_cache.json so re-runs are fast.
"""

import hashlib
import json
import os
import statistics
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import numpy as np
from langchain_core.documents import Document
from langchain_openai import AzureOpenAIEmbeddings
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from src.rag.chunker import DocumentChunker

GUIDES_DIR = (
    Path(__file__).resolve().parents[1] / "knowledge_base" / "destination_guides"
)
CACHE_FILE = Path(__file__).parent / ".eval_cache.json"

# ── Ground-truth eval set ────────────────────────────────────────────────
EVAL_SET = [
    ("best street food stalls in Bangkok", "bangkok.md", "BKK food"),
    ("Thai cuisine dishes to try", "bangkok.md", "BKK cuisine"),
    ("night markets for eating cheap", "bangkok.md", "BKK night market"),
    ("how to get around Bangkok by train", "bangkok.md", "BKK transport"),
    ("BTS Skytrain routes and fares", "bangkok.md", "BKK BTS"),
    ("Buddhist temples worth visiting", "bangkok.md", "BKK temples"),
    ("Wat Pho reclining Buddha", "bangkok.md", "BKK Wat Pho"),
    ("things to do in Wroclaw old town", "wroclaw.md", "WRO old town"),
    ("where to sleep in Wroclaw budget hostel", "wroclaw.md", "WRO sleep"),
    ("Wroclaw dwarfs gnomes attractions", "wroclaw.md", "WRO dwarfs"),
    ("best beaches in Cancun", "cancun.md", "CUN beaches"),
    ("Cancun hotel zone restaurants", "cancun.md", "CUN dining"),
    ("cenotes near Cancun day trip", "cancun.md", "CUN cenotes"),
    ("visa requirements and entry", None, "cross — entry"),
    ("budget tips save money", None, "cross — budget"),
]


# ── Embedding cache ──────────────────────────────────────────────────────


class EmbeddingCache:
    """Persist embeddings to disk so re-runs are instant."""

    def __init__(self, path: Path, use_cache: bool = True):
        self.path = path
        self.use_cache = use_cache
        self._store: dict[str, list[float]] = {}
        if use_cache and path.exists():
            self._store = json.loads(path.read_text())
            print(f"  Loaded {len(self._store)} cached embeddings from {path.name}")

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def get_or_embed(
        self, texts: list[str], model: AzureOpenAIEmbeddings
    ) -> list[list[float]]:
        missing = [t for t in texts if self._key(t) not in self._store]
        if missing:
            print(
                f"  Embedding {len(missing)} new texts (cached: {len(texts) - len(missing)}) …",
                end=" ",
                flush=True,
            )
            # Batch in groups of 100 to avoid token limits
            for i in range(0, len(missing), 100):
                batch = missing[i : i + 100]
                vecs = model.embed_documents(batch)
                for text, vec in zip(batch, vecs):
                    self._store[self._key(text)] = vec
                print(f"{i + len(batch)}/{len(missing)}", end=" ", flush=True)
            print("done")
            if self.use_cache:
                self.path.write_text(json.dumps(self._store))
        return [self._store[self._key(t)] for t in texts]

    def embed_query(self, query: str, model: AzureOpenAIEmbeddings) -> list[float]:
        return self.get_or_embed([query], model)[0]


# ── Wraps AzureOpenAIEmbeddings with cache for SemanticChunker ──────────


class CachedEmbeddings:
    """Drop-in wrapper that intercepts embed_documents calls through the cache."""

    def __init__(self, model: AzureOpenAIEmbeddings, cache: EmbeddingCache):
        self._model = model
        self._cache = cache

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._cache.get_or_embed(texts, self._model)

    def embed_query(self, text: str) -> list[float]:
        return self._cache.embed_query(text, self._model)

    # SemanticChunker accesses these attributes
    def __getattr__(self, name):
        return getattr(self._model, name)


# ── Load guides ──────────────────────────────────────────────────────────


def load_raw_docs() -> list[Document]:
    return [
        Document(
            page_content=p.read_text(encoding="utf-8"), metadata={"source": p.name}
        )
        for p in sorted(GUIDES_DIR.glob("*.md"))
    ]


# ── Chunking strategies ──────────────────────────────────────────────────


def chunk_fixed(docs: list[Document]) -> list[Document]:
    """Strategy A: Fixed-size — simple, predictable, no embedding needed."""
    return RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " "],
    ).split_documents(docs)


def chunk_semantic(
    docs: list[Document], embeddings, threshold: int, min_size: int
) -> list[Document]:
    chunker = SemanticChunker(
        embeddings,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=threshold,
        min_chunk_size=min_size,
    )
    chunks = []
    for doc in docs:
        chunks.extend(
            chunker.create_documents([doc.page_content], metadatas=[doc.metadata])
        )
    return chunks


_SECTION_NAMES = {
    "Understand",
    "Get in",
    "Get around",
    "See",
    "Do",
    "Buy",
    "Eat",
    "Drink",
    "Sleep",
    "Stay safe",
    "Stay healthy",
    "Connect",
    "Cope",
    "Go next",
    "Respect",
    "Talk",
    "Learn",
    "Work",
    "Budget",
    "Mid-range",
    "Splurge",
    "By plane",
    "By train",
    "By bus",
    "By car",
    "By boat",
    "By taxi",
    "By metro",
    "By bicycle",
}
_SECTION_PAT = re.compile(
    r"^("
    + "|".join(re.escape(n) for n in sorted(_SECTION_NAMES, key=len, reverse=True))
    + r")\s*$",
    re.MULTILINE,
)


def chunk_section(
    docs: list[Document],
    min_chars: int = 200,
    max_chars: int = 3000,
) -> list[Document]:
    """Strategy D: Section-level — split on Wikivoyage bare-text headings.

    Wikivoyage markdown uses bare lines like ``Eat``, ``Sleep``, ``Get in``
    as section headings (no ``#`` prefix).  This splitter detects those lines
    and makes each section a chunk.  Sections < *min_chars* are merged into
    the next; sections > *max_chars* are sub-split at paragraph boundaries.
    """
    chunks: list[Document] = []
    for doc in docs:
        lines = doc.page_content.split("\n")
        sections: list[str] = []
        current_lines: list[str] = []

        for line in lines:
            if _SECTION_PAT.match(line):
                # Flush previous section
                if current_lines:
                    sections.append("\n".join(current_lines).strip())
                current_lines = [line]
            else:
                current_lines.append(line)
        if current_lines:
            sections.append("\n".join(current_lines).strip())

        # Merge small sections, sub-split large ones
        merged: list[str] = []
        buf = ""
        for sec in sections:
            if not sec:
                continue
            buf = (buf + "\n\n" + sec).strip() if buf else sec
            if len(buf) >= min_chars:
                merged.append(buf)
                buf = ""
        if buf:
            if merged:
                merged[-1] += "\n\n" + buf
            else:
                merged.append(buf)

        # Sub-split oversized sections at paragraph boundaries
        final: list[str] = []
        for sec in merged:
            if len(sec) <= max_chars:
                final.append(sec)
            else:
                paragraphs = sec.split("\n\n")
                cur = ""
                for p in paragraphs:
                    candidate = (cur + "\n\n" + p).strip() if cur else p.strip()
                    if len(candidate) > max_chars and cur:
                        final.append(cur.strip())
                        cur = p.strip()
                    else:
                        cur = candidate
                if cur.strip():
                    final.append(cur.strip())

        for text in final:
            chunks.append(
                Document(
                    page_content=text,
                    metadata={**doc.metadata},
                )
            )
    return chunks


def chunk_page(docs: list[Document], page_chars: int = 3000) -> list[Document]:
    """Strategy E: Page-level (NVIDIA style) — fixed-size at paragraph breaks.

    Simulates NVIDIA's page-level chunking for markdown (no real pages).
    Splits into ~page_chars blocks, always breaking at the nearest paragraph
    boundary (\n\n) so no sentence is cut mid-way.
    """
    chunks = []
    for doc in docs:
        paragraphs = doc.page_content.split("\n\n")
        current = ""
        for para in paragraphs:
            candidate = (current + "\n\n" + para).strip() if current else para.strip()
            if len(candidate) > page_chars and current:
                chunks.append(
                    Document(
                        page_content=current.strip(),
                        metadata={**doc.metadata},
                    )
                )
                current = para.strip()
            else:
                current = candidate
        if current.strip():
            chunks.append(
                Document(
                    page_content=current.strip(),
                    metadata={**doc.metadata},
                )
            )
    return chunks


# ── In-memory vector store ───────────────────────────────────────────────


class SimpleVectorStore:
    def __init__(self, docs: list[Document], embeddings: CachedEmbeddings):
        self.docs = docs
        texts = [d.page_content for d in docs]
        vecs = embeddings.embed_documents(texts)
        mat = np.array(vecs, dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        self.matrix = mat / np.maximum(norms, 1e-10)
        self._emb = embeddings

    def query(self, query_text: str, top_k: int = 3):
        q = np.array(self._emb.embed_query(query_text), dtype=np.float32)
        q = q / max(float(np.linalg.norm(q)), 1e-10)
        scores = self.matrix @ q
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [(self.docs[i], float(scores[i])) for i in top_idx]


# ── Evaluation ───────────────────────────────────────────────────────────


def evaluate(store: SimpleVectorStore, strategy_name: str) -> dict:
    hits1 = hits3 = 0
    scores_top1 = []
    noise_count = 0

    for query, expected_src, _ in EVAL_SET:
        results = store.query(query, top_k=3)
        top_scores = [s for _, s in results]
        top_sources = [d.metadata.get("source") for d, _ in results]

        scores_top1.append(top_scores[0])
        noise_count += sum(1 for s in top_scores if s < 0.4)

        if expected_src is None:
            continue
        if top_sources[0] == expected_src:
            hits1 += 1
        if expected_src in top_sources:
            hits3 += 1

    n = sum(1 for q in EVAL_SET if q[1] is not None)
    return {
        "strategy": strategy_name,
        "hits@1": hits1 / n,
        "hits@3": hits3 / n,
        "avg_score": statistics.mean(scores_top1),
        "min_score": min(scores_top1),
        "noise_rate": noise_count / (len(EVAL_SET) * 3),
    }


def chunk_stats(chunks: list[Document]) -> dict:
    lengths = [len(d.page_content) for d in chunks]
    return {
        "count": len(chunks),
        "avg": int(statistics.mean(lengths)),
        "min": min(lengths),
        "max": max(lengths),
        "stdev": int(statistics.stdev(lengths)) if len(lengths) > 1 else 0,
    }


def detailed_report(store: SimpleVectorStore, strategy_name: str):
    print(f"\n{'─' * 70}")
    print(f"  Per-query detail — {strategy_name}")
    print(f"{'─' * 70}")
    for query, expected_src, label in EVAL_SET:
        results = store.query(query, top_k=3)
        top_src = results[0][0].metadata.get("source")
        hit = (
            "✓"
            if (expected_src and top_src == expected_src)
            else ("–" if not expected_src else "✗")
        )
        print(f'\n  [{hit}] {label}: "{query}"')
        for i, (doc, score) in enumerate(results, 1):
            src = doc.metadata.get("source", "?")
            snippet = doc.page_content[:90].replace("\n", " ")
            flag = (
                " ← WRONG" if (expected_src and i == 1 and src != expected_src) else ""
            )
            print(f"      {i}. [{score:.3f}] {src}: {snippet}…{flag}")


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    use_cache = "--no-cache" not in sys.argv
    skip_semantic = "--skip-semantic" in sys.argv

    print("=" * 70)
    print("  Wanderlisted — RAG Chunking Strategy Evaluator")
    print("=" * 70)

    docs = load_raw_docs()
    print(f"\nLoaded {len(docs)} guides: {[d.metadata['source'] for d in docs]}")

    cache = EmbeddingCache(CACHE_FILE, use_cache=use_cache)
    model = AzureOpenAIEmbeddings(
        azure_deployment=os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )
    embeddings = CachedEmbeddings(model, cache)

    results = []

    # ── Strategy A ───────────────────────────────────────────────────────
    print("\n[A] Fixed-size (800 chars, 100 overlap) — no embedding for splitting")
    chunks_a = chunk_fixed(docs)
    stats_a = chunk_stats(chunks_a)
    print(
        f"    {stats_a['count']} chunks | avg={stats_a['avg']} min={stats_a['min']} max={stats_a['max']} stdev={stats_a['stdev']}"
    )
    store_a = SimpleVectorStore(chunks_a, embeddings)
    results.append((evaluate(store_a, "A: Fixed"), stats_a, store_a))

    # ── Strategy B ───────────────────────────────────────────────────────
    if skip_semantic:
        print("\n[B] Semantic conservative — SKIPPED (--skip-semantic)")
    else:
        print("\n[B] Semantic conservative (threshold=70, min=300)")
        chunks_b = chunk_semantic(docs, embeddings, threshold=70, min_size=300)
        stats_b = chunk_stats(chunks_b)
        print(
            f"    {stats_b['count']} chunks | avg={stats_b['avg']} min={stats_b['min']} max={stats_b['max']} stdev={stats_b['stdev']}"
        )
        store_b = SimpleVectorStore(chunks_b, embeddings)
        results.append(
            (evaluate(store_b, "B: Semantic conservative"), stats_b, store_b)
        )

    # ── Strategy C ───────────────────────────────────────────────────────
    if skip_semantic:
        print("[C] Semantic aggressive — SKIPPED (--skip-semantic)")
    else:
        print("\n[C] Semantic aggressive (threshold=60, min=150)")
        chunks_c = chunk_semantic(docs, embeddings, threshold=60, min_size=150)
        stats_c = chunk_stats(chunks_c)
        print(
            f"    {stats_c['count']} chunks | avg={stats_c['avg']} min={stats_c['min']} max={stats_c['max']} stdev={stats_c['stdev']}"
        )
        store_c = SimpleVectorStore(chunks_c, embeddings)
        results.append((evaluate(store_c, "C: Semantic aggressive"), stats_c, store_c))

    # ── Strategy D ───────────────────────────────────────────────────────
    print(
        "\n[D] Section-level (## headers, min=200 chars) — no embedding for splitting"
    )
    chunks_d = chunk_section(docs, min_chars=200)
    stats_d = chunk_stats(chunks_d)
    print(
        f"    {stats_d['count']} chunks | avg={stats_d['avg']} min={stats_d['min']} max={stats_d['max']} stdev={stats_d['stdev']}"
    )
    store_d = SimpleVectorStore(chunks_d, embeddings)
    results.append((evaluate(store_d, "D: Section-level"), stats_d, store_d))

    # ── Strategy E ───────────────────────────────────────────────────────
    print(
        "\n[E] Page-level NVIDIA (~3000 chars at paragraph breaks) — no embedding for splitting"
    )
    chunks_e = chunk_page(docs, page_chars=3000)
    stats_e = chunk_stats(chunks_e)
    print(
        f"    {stats_e['count']} chunks | avg={stats_e['avg']} min={stats_e['min']} max={stats_e['max']} stdev={stats_e['stdev']}"
    )
    store_e = SimpleVectorStore(chunks_e, embeddings)
    results.append((evaluate(store_e, "E: Page-level (NVIDIA)"), stats_e, store_e))

    # ── Strategy F ───────────────────────────────────────────────────────
    print("\n[F] DocumentChunker (section + merge/subsplit + metadata)")
    dc = DocumentChunker(
        logger_name="eval.chunker",
        default_chunk_size=2000,
        default_chunk_overlap=200,
        min_chunk_size=200,
        max_section_size=3000,
    )
    chunks_f = dc.chunk_documents(docs)
    stats_f = chunk_stats(chunks_f)
    print(
        f"    {stats_f['count']} chunks | avg={stats_f['avg']} min={stats_f['min']} max={stats_f['max']} stdev={stats_f['stdev']}"
    )
    store_f = SimpleVectorStore(chunks_f, embeddings)
    results.append((evaluate(store_f, "F: DocumentChunker"), stats_f, store_f))

    # ── Summary table ────────────────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    print(
        f"{'Strategy':<28} {'Chunks':>6} {'Avg':>5} {'Hits@1':>7} {'Hits@3':>7} {'AvgScore':>9} {'Noise%':>7}"
    )
    print("─" * 70)
    for ev, st, _ in results:
        print(
            f"{ev['strategy']:<28} {st['count']:>6} {st['avg']:>5} "
            f"{ev['hits@1']:>6.0%}  {ev['hits@3']:>6.0%}  "
            f"{ev['avg_score']:>8.3f}  {ev['noise_rate']:>6.0%}"
        )

    # ── Per-query detail for best strategy ───────────────────────────────
    best_ev, _, best_store = max(
        results, key=lambda r: r[0]["hits@1"] * 0.5 + r[0]["avg_score"] * 0.5
    )
    detailed_report(best_store, best_ev["strategy"])

    print("\n\n" + "=" * 70)
    print("  HOW TO READ THESE RESULTS")
    print("=" * 70)
    print(
        textwrap.dedent("""
  Hits@1   — correct source ranked #1. Target: ≥ 80%
  Hits@3   — correct source appears in top 3. Target: ≥ 95%
  AvgScore — mean cosine similarity of top result. Target: ≥ 0.65
  Noise%   — fraction of top-3 results with score < 0.4. Target: < 15%

  When to choose each strategy:
  ─────────────────────────────
  Fixed-size     Best for structured docs (FAQs, menus, tables). Breaks
  (chunk_size)   mid-sentence so topic context is sometimes cut. Fast and
                 free — no embedding calls needed for splitting.

  Semantic cons. Aligns splits to topic changes detected by embedding
  (threshold 70)  similarity. Better for narrative travel guides where
                 sections flow together. Use when AvgScore > Fixed.

  Semantic aggr. More chunks = finer grain retrieval, but higher embedding
  (threshold 60)  cost and more noise. Use when Hits@3 > Hits@1 across
                 strategies (right content exists but is buried).

  Section-level  Splits on markdown ## headers. Each topic (Eat, Sleep,
  (## headers)   See, Get around) becomes one chunk. Best for docs with
                 clear heading structure. Free — no API calls.

  Page-level     NVIDIA's top strategy: fixed-size blocks (~3000 chars)
  (NVIDIA)       split at paragraph boundaries. Simulates a "printed page."
                 Uniform sizes + no mid-sentence cuts. Free — no API calls.
                 Difference from section-level: ignores headings, uses
                 paragraph proximity instead. Better when sections vary
                 wildly in length (some 200 chars, some 5000+).
    """)
    )

    print("  Re-run without cache:  python scripts/eval_rag.py --no-cache")
    print(f"  Cached embeddings at:  {CACHE_FILE}\n")


if __name__ == "__main__":
    main()
