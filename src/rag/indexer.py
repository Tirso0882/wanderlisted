"""RAG indexer — builds and syncs a Pinecone vector index from destination guides.

Uses hash-based staleness detection: the index is only re-embedded when
source documents change.  Pinecone is a managed cloud vector database so
there is no local index to persist — only a manifest of file hashes is
cached locally.

Chunking strategy: **semantic chunking** via ``SemanticChunker`` — splits
documents at natural topic boundaries detected by embedding similarity
rather than fixed character counts.
"""

import hashlib
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import AzureOpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import NotFoundException

load_dotenv()

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────
GUIDES_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / "destination_guides"
CACHE_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / ".cache"
MANIFEST_PATH = CACHE_DIR / "manifest.json"

# ── Pinecone config ─────────────────────────────────────────────────────
INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "wanderlisted-guides")
EMBEDDING_DIMENSION = 3072  # text-embedding-3-large default output dimension
NAMESPACE = "destination_guides"

# ── Semantic chunking config ─────────────────────────────────────────────
BREAKPOINT_TYPE = "percentile"
BREAKPOINT_THRESHOLD = 70   # was 85 — splits at top 30% dissimilar boundaries (more chunks)
MIN_CHUNK_SIZE = 300        # was 200 — avoid tiny noise chunks like podcast blurbs


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


def _get_embeddings() -> AzureOpenAIEmbeddings:
    """Create the Azure OpenAI embeddings model."""
    return AzureOpenAIEmbeddings(
        azure_deployment=os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )


def _get_pinecone_index():
    """Get or create the Pinecone index."""
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

    if INDEX_NAME not in [idx.name for idx in pc.list_indexes()]:
        logger.info("Creating Pinecone index '%s' …", INDEX_NAME)
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=os.environ.get("PINECONE_CLOUD", "aws"),
                region=os.environ.get("PINECONE_REGION", "us-east-1"),
            ),
        )

    return pc.Index(INDEX_NAME)


def _load_and_split(guides_dir: Path, embeddings: AzureOpenAIEmbeddings) -> list[Document]:
    """Read all .md files and apply semantic chunking.

    Uses ``SemanticChunker`` which computes embeddings for each sentence,
    then splits where the cosine similarity between consecutive sentence
    groups drops below the configured percentile threshold.  This produces
    chunks aligned to natural topic boundaries rather than arbitrary
    character counts.
    """
    chunker = SemanticChunker(
        embeddings,
        breakpoint_threshold_type=BREAKPOINT_TYPE,
        breakpoint_threshold_amount=BREAKPOINT_THRESHOLD,
        min_chunk_size=MIN_CHUNK_SIZE,
    )

    documents: list[Document] = []
    for path in sorted(guides_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        metadata = {"source": path.name}
        chunks = chunker.create_documents([text], metadatas=[metadata])
        documents.extend(chunks)

    return documents


# ── Public API ───────────────────────────────────────────────────────────

def build_index(guides_dir: Path | None = None):
    """Build (or skip if fresh) the Pinecone vector index.

    Returns the Pinecone ``Index`` object and the embeddings model as a
    tuple ``(index, embeddings)`` — or ``None`` when *guides_dir* has no
    markdown files.
    """
    guides_dir = guides_dir or GUIDES_DIR

    if not any(guides_dir.glob("*.md")):
        logger.warning("No .md files found in %s — RAG disabled", guides_dir)
        return None

    embeddings = _get_embeddings()
    index = _get_pinecone_index()

    # Fast path: manifest matches — skip re-embedding
    if not _is_stale(guides_dir):
        logger.info("✓ Pinecone index up-to-date — skipping re-embed")
        return index, embeddings

    # Slow path: re-embed and upsert
    logger.info("✗ Source documents changed — re-embedding into Pinecone …")
    documents = _load_and_split(guides_dir, embeddings)
    logger.info("  Loaded %d chunks from %s", len(documents), guides_dir)

    # Clear existing vectors in namespace before upserting
    # (namespace may not exist yet on a fresh index — that's fine)
    try:
        index.delete(delete_all=True, namespace=NAMESPACE)
    except NotFoundException:
        logger.debug("Namespace '%s' not found — skipping delete (first run)", NAMESPACE)

    # Embed and upsert in batches of 100
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        texts = [doc.page_content for doc in batch]
        metadatas = [doc.metadata for doc in batch]
        vectors = embeddings.embed_documents(texts)

        upsert_data = []
        for j, (vec, text, meta) in enumerate(zip(vectors, texts, metadatas)):
            upsert_data.append({
                "id": f"chunk-{i + j}",
                "values": vec,
                "metadata": {**meta, "text": text},
            })
        index.upsert(vectors=upsert_data, namespace=NAMESPACE)

    # Save manifest
    _save_manifest(guides_dir)
    logger.info("  Upserted %d vectors into Pinecone '%s'", len(documents), INDEX_NAME)

    return index, embeddings


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    result = build_index()
    if result is None:
        print("No guides found — nothing indexed.")
    else:
        index, _ = result
        stats = index.describe_index_stats()
        ns = stats.get("namespaces", {}).get(NAMESPACE, {})
        print(f"\nPinecone index '{INDEX_NAME}' — {ns.get('vector_count', '?')} vectors in namespace '{NAMESPACE}'")
