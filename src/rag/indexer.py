"""RAG indexer — builds and syncs a Pinecone vector index from destination guides.

Uses hash-based staleness detection: the index is only re-embedded when
source documents change.  Pinecone is a managed cloud vector database so
there is no local index to persist — only a manifest of file hashes is
cached locally.

Chunking strategy: **section-level** via ``DocumentChunker`` — splits on
Wikivoyage bare-text headings (Eat, Sleep, Get around …) with recursive
character fallback for documents without section headings (future PDFs).
"""

import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import NotFoundException

from custom_logging import AppLogger
from src.rag.chunker import DocumentChunker
from src.rag.embeddings import EmbeddingGenerator

load_dotenv()

logger = AppLogger(logger_name="rag.indexer", level="DEBUG")

# ── Paths ────────────────────────────────────────────────────────────────
GUIDES_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / "destination_guides"
CACHE_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / ".cache"
MANIFEST_PATH = CACHE_DIR / "manifest.json"

# ── Pinecone config ─────────────────────────────────────────────────────
INDEX_NAME = os.environ["PINECONE_INDEX_NAME"]
NAMESPACE = "destination_guides"


# ── Helpers ──────────────────────────────────────────────────────────────

def _hash_file(path: Path) -> str:
    """SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def _compute_manifest(guides_dir: Path) -> dict[str, str]:
    """Map every .md file in *guides_dir* to its SHA-256 hash."""
    manifest: dict[str, str] = {}
    for p in sorted(guides_dir.glob("*.md")):
        manifest[p.name] = _hash_file(p)
    return manifest


def _is_stale(guides_dir: Path) -> bool:
    """Return True if the index needs rebuilding."""
    if not MANIFEST_PATH.exists():
        return True
    with open(MANIFEST_PATH) as f:
        cached = json.load(f)
    return _compute_manifest(guides_dir) != cached


def _save_manifest(guides_dir: Path) -> None:
    """Persist the current file-hash manifest."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(_compute_manifest(guides_dir), f, indent=2)


def _get_embedding_generator() -> EmbeddingGenerator:
    """Create the embedding generator using the configured provider."""
    return EmbeddingGenerator()


def _get_pinecone_index(embedding_dim: int | None = None):
    """Get or create the Pinecone index."""
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    dim = embedding_dim or int(os.environ.get("EMBEDDING_DIMENSION", "3072"))

    if INDEX_NAME not in [idx.name for idx in pc.list_indexes()]:
        logger.info(f"Creating Pinecone index '{INDEX_NAME}' …")
        pc.create_index(
            name=INDEX_NAME,
            dimension=dim,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=os.environ["PINECONE_CLOUD"],
                region=os.environ["PINECONE_REGION"],
            ),
        )

    return pc.Index(INDEX_NAME)


def _load_and_chunk(guides_dir: Path) -> list[Document]:
    """Read all .md files and chunk with section-level splitting."""
    chunker = DocumentChunker(
        logger_name="rag.chunker",
        default_chunk_size=2000,
        default_chunk_overlap=200,
        min_chunk_size=200,
        max_section_size=3000,
    )

    documents: list[Document] = []
    for path in sorted(guides_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        doc = Document(page_content=text, metadata={"source": path.name})
        chunks = chunker.chunk_documents(doc)
        documents.extend(chunks)

    return documents


# ── Public API ───────────────────────────────────────────────────────────

def build_index(guides_dir: Path | None = None):
    """Build (or skip if fresh) the Pinecone vector index.

    Returns ``(index, embedding_generator)`` or ``None`` when *guides_dir*
    has no markdown files.
    """
    guides_dir = guides_dir or GUIDES_DIR

    if not any(guides_dir.glob("*.md")):
        logger.warning(f"No .md files found in {guides_dir} — RAG disabled")
        return None

    emb_gen = _get_embedding_generator()
    index = _get_pinecone_index(emb_gen.config.dimensions)

    # Fast path: manifest matches — skip re-embedding
    if not _is_stale(guides_dir):
        logger.info("✓ Pinecone index up-to-date — skipping re-embed")
        return index, emb_gen

    # Slow path: re-chunk, re-embed and upsert
    logger.info("✗ Source documents changed — re-indexing into Pinecone …")
    documents = _load_and_chunk(guides_dir)
    logger.info(f"  Loaded {len(documents)} chunks from {guides_dir}")

    # Clear existing vectors in namespace before upserting
    try:
        index.delete(delete_all=True, namespace=NAMESPACE)
    except NotFoundException:
        logger.debug(f"Namespace '{NAMESPACE}' not found — skipping delete (first run)")

    # Embed and upsert in batches
    batch_size = emb_gen.config.batch_size
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        texts = [doc.page_content for doc in batch]
        metadatas = [doc.metadata for doc in batch]
        vectors = emb_gen.embed_documents(texts)

        upsert_data = []
        for j, (vec, text, meta) in enumerate(zip(vectors, texts, metadatas)):
            upsert_data.append({
                "id": f"chunk-{i + j}",
                "values": vec,
                "metadata": {**meta, "text": text},
            })
        index.upsert(vectors=upsert_data, namespace=NAMESPACE)

    _save_manifest(guides_dir)
    logger.info(f"  Upserted {len(documents)} vectors into Pinecone '{INDEX_NAME}'")

    return index, emb_gen


if __name__ == "__main__":
    result = build_index()
    if result is None:
        print("No guides found — nothing indexed.")
    else:
        index, _ = result
        stats = index.describe_index_stats()
        ns = stats.get("namespaces", {}).get(NAMESPACE, {})
        print(f"\nPinecone index '{INDEX_NAME}' — {ns.get('vector_count', '?')} vectors in namespace '{NAMESPACE}'")
