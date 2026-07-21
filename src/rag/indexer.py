"""RAG indexer — builds and syncs a Pinecone vector index.

Supports **multi-tenant** namespaces so each client gets isolated content:
    - ``<tenant>/destination_guides``  — client-provided brochures / guides
    - ``wikivoyage/destination_guides`` — community fallback (Wikivoyage)

When a tenant has no content for a destination, the retrieval layer falls
back to the Wikivoyage namespace automatically.

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

# Shells and entry points own runtime overrides such as EDD tracing policy.
load_dotenv()

logger = AppLogger(logger_name="rag.indexer", level="DEBUG")

# ── Paths ────────────────────────────────────────────────────────────────
GUIDES_DIR = (
    Path(__file__).resolve().parents[2] / "knowledge_base" / "destination_guides"
)
CACHE_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / ".cache"
MANIFEST_PATH = CACHE_DIR / "manifest.json"

# ── Pinecone config ─────────────────────────────────────────────────────
INDEX_NAME = os.environ["PINECONE_INDEX_NAME"]

# Multi-tenant namespace: "<tenant>/destination_guides"
# Default tenant is "wikivoyage" for the community fallback content.
DEFAULT_TENANT = "wikivoyage"
NAMESPACE = "destination_guides"  # kept for backward compat imports


def namespace_for(tenant: str | None = None) -> str:
    """Build a Pinecone namespace string for *tenant*.

    Examples:
        ``namespace_for()``          → ``"wikivoyage/destination_guides"``
        ``namespace_for("acme")``    → ``"acme/destination_guides"``
    """
    tenant = (tenant or DEFAULT_TENANT).strip().lower().replace(" ", "_")
    return f"{tenant}/destination_guides"


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


def build_index(
    guides_dir: Path | None = None,
    *,
    tenant: str | None = None,
):
    """Build (or skip if fresh) the Pinecone vector index.

    Args:
        guides_dir: Directory containing ``.md`` files to index.
        tenant: Client tenant ID (e.g. ``"acme_travel"``).  Defaults to
                ``"wikivoyage"`` for the community fallback content.

    Returns ``(index, embedding_generator)`` or ``None`` when *guides_dir*
    has no markdown files.
    """
    guides_dir = guides_dir or GUIDES_DIR
    ns = namespace_for(tenant)

    if not any(guides_dir.glob("*.md")):
        logger.warning(f"No .md files found in {guides_dir} — RAG disabled")
        return None

    emb_gen = _get_embedding_generator()
    dim = int(
        os.environ.get(
            "AZURE_OPENAI_EMBEDDING_DIMENSIONS",
            os.environ.get("EMBEDDING_DIMENSION", "3072"),
        )
    )
    index = _get_pinecone_index(dim)

    # Fast path: manifest matches — skip re-embedding
    if not _is_stale(guides_dir):
        logger.info(f"✓ Pinecone index up-to-date for '{ns}' — skipping re-embed")
        return index, emb_gen

    # Slow path: re-chunk, re-embed and upsert
    logger.info(
        f"✗ Source documents changed — re-indexing into Pinecone namespace '{ns}' …"
    )
    documents = _load_and_chunk(guides_dir)
    logger.info(f"  Loaded {len(documents)} chunks from {guides_dir}")

    # Clear existing vectors in namespace before upserting
    try:
        index.delete(delete_all=True, namespace=ns)
    except NotFoundException:
        logger.debug(f"Namespace '{ns}' not found — skipping delete (first run)")

    # Embed and upsert in batches
    batch_size = emb_gen.config.batch_size
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        texts = [doc.page_content for doc in batch]
        metadatas = [doc.metadata for doc in batch]
        vectors = emb_gen.embed_documents(texts)

        upsert_data = []
        for j, (vec, text, meta) in enumerate(zip(vectors, texts, metadatas)):
            upsert_data.append(
                {
                    "id": f"chunk-{i + j}",
                    "values": vec,
                    "metadata": {
                        **meta,
                        "text": text,
                        "tenant": tenant or DEFAULT_TENANT,
                    },
                }
            )
        index.upsert(vectors=upsert_data, namespace=ns)

    _save_manifest(guides_dir)
    logger.info(
        f"  Upserted {len(documents)} vectors into Pinecone '{INDEX_NAME}' namespace '{ns}'"
    )

    return index, emb_gen


if __name__ == "__main__":
    import sys

    tenant = sys.argv[1] if len(sys.argv) > 1 else None
    result = build_index(tenant=tenant)
    if result is None:
        print("No guides found — nothing indexed.")
    else:
        index, _ = result
        ns_name = namespace_for(tenant)
        stats = index.describe_index_stats()
        ns = stats.get("namespaces", {}).get(ns_name, {})
        print(
            f"\nPinecone index '{INDEX_NAME}' — {ns.get('vector_count', '?')} vectors in namespace '{ns_name}'"
        )
