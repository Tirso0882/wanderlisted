"""Tests for src/rag/indexer.py — vector index building + staleness detection."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from src.rag.indexer import (
    _compute_manifest,
    _hash_file,
    _is_stale,
    _load_and_split,
    build_index,
    NAMESPACE,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def guides_dir(tmp_path):
    """Create a temp directory with two small markdown guides."""
    d = tmp_path / "guides"
    d.mkdir()
    (d / "japan_guide.md").write_text(
        "# Japan\n\n## Tokyo\nGreat city.\n\n## Kyoto\nTemples everywhere."
    )
    (d / "france_guide.md").write_text(
        "# France\n\n## Paris\nEiffel Tower.\n\n## Lyon\nFood capital."
    )
    return d


@pytest.fixture
def large_guide_dir(tmp_path):
    """Create a temp directory with one large markdown file with real sentences."""
    d = tmp_path / "guides"
    d.mkdir()
    # SemanticChunker splits on sentence boundaries, so use real sentences.
    paragraphs = [
        f"## Section {i}\n\nThis is a detailed travel guide section about region {i}. "
        f"There are many attractions to see in this area. Visitors enjoy the local food "
        f"and culture. Public transport is convenient and affordable. "
        f"Hotels range from budget hostels to luxury resorts.\n"
        for i in range(30)
    ]
    (d / "big_guide.md").write_text("\n".join(paragraphs))
    return d


@pytest.fixture
def mock_embeddings():
    """Mock embeddings with clustered similarities and clear breakpoints.

    SemanticChunker splits when cosine similarity between consecutive
    sentences drops below a percentile threshold.  We create clusters of
    similar vectors with abrupt direction changes between clusters so that
    breakpoints are detected reliably.
    """
    emb = MagicMock()

    def _embed(texts):
        # Create 5 clusters of ~equal size with distinct directions
        n = len(texts)
        cluster_size = max(n // 5, 1)
        directions = [
            [1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0],
        ]
        vecs = []
        for i in range(n):
            cluster_idx = min(i // cluster_size, 4)
            # Add small noise within cluster to keep them similar
            vec = directions[cluster_idx][:]
            vec[cluster_idx] += (i % cluster_size) * 0.01
            vecs.append(vec)
        return vecs

    emb.embed_documents.side_effect = _embed
    return emb


# ── _hash_file ───────────────────────────────────────────────────────────

class TestHashFile:
    def test_consistent_hash(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello world")
        assert _hash_file(f) == _hash_file(f)

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.md"
        f2 = tmp_path / "b.md"
        f1.write_text("hello")
        f2.write_text("world")
        assert _hash_file(f1) != _hash_file(f2)


# ── _compute_manifest ────────────────────────────────────────────────────

class TestComputeManifest:
    def test_manifest_lists_all_md_files(self, guides_dir):
        manifest = _compute_manifest(guides_dir)
        assert set(manifest.keys()) == {"france_guide.md", "japan_guide.md"}

    def test_manifest_ignores_non_md(self, guides_dir):
        (guides_dir / "notes.txt").write_text("not a guide")
        manifest = _compute_manifest(guides_dir)
        assert "notes.txt" not in manifest

    def test_manifest_changes_when_file_changes(self, guides_dir):
        m1 = _compute_manifest(guides_dir)
        (guides_dir / "japan_guide.md").write_text("Updated content")
        m2 = _compute_manifest(guides_dir)
        assert m1["japan_guide.md"] != m2["japan_guide.md"]
        assert m1["france_guide.md"] == m2["france_guide.md"]


# ── _is_stale ────────────────────────────────────────────────────────────

class TestIsStale:
    def test_stale_when_no_cache(self, guides_dir):
        """No manifest → always stale."""
        assert _is_stale(guides_dir) is True

    def test_not_stale_when_manifest_matches(self, guides_dir, tmp_path):
        """Write matching manifest → not stale."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        manifest_path = cache_dir / "manifest.json"

        manifest = _compute_manifest(guides_dir)
        manifest_path.write_text(json.dumps(manifest))

        with patch("src.rag.indexer.MANIFEST_PATH", manifest_path):
            assert _is_stale(guides_dir) is False

    def test_stale_when_file_added(self, guides_dir, tmp_path):
        """Add a new file → stale."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        manifest_path = cache_dir / "manifest.json"

        manifest = _compute_manifest(guides_dir)
        manifest_path.write_text(json.dumps(manifest))

        # Add a new file
        (guides_dir / "italy_guide.md").write_text("# Italy")

        with patch("src.rag.indexer.MANIFEST_PATH", manifest_path):
            assert _is_stale(guides_dir) is True


# ── _load_and_split ──────────────────────────────────────────────────────

class TestLoadAndSplit:
    def test_produces_chunks_with_metadata(self, guides_dir, mock_embeddings):
        """Semantic chunking should produce documents with source metadata."""
        docs = _load_and_split(guides_dir, mock_embeddings)
        assert len(docs) >= 2  # At least one chunk per file
        assert all(d.metadata["source"].endswith(".md") for d in docs)

    def test_large_doc_is_chunked(self, large_guide_dir, mock_embeddings):
        """Large docs should be split into multiple chunks."""
        docs = _load_and_split(large_guide_dir, mock_embeddings)
        assert len(docs) > 1
        assert all(d.metadata["source"] == "big_guide.md" for d in docs)

    def test_empty_dir_returns_empty(self, tmp_path, mock_embeddings):
        """Empty directory → no documents."""
        d = tmp_path / "empty"
        d.mkdir()
        assert _load_and_split(d, mock_embeddings) == []

    def test_metadata_includes_source(self, guides_dir, mock_embeddings):
        docs = _load_and_split(guides_dir, mock_embeddings)
        sources = {d.metadata["source"] for d in docs}
        assert "japan_guide.md" in sources
        assert "france_guide.md" in sources


# ── build_index ──────────────────────────────────────────────────────────

class TestBuildIndex:
    def test_returns_none_when_no_guides(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert build_index(d) is None

    @patch("src.rag.indexer._load_and_split")
    @patch("src.rag.indexer._get_pinecone_index")
    @patch("src.rag.indexer._get_embeddings")
    def test_builds_index_when_stale(self, mock_get_emb, mock_get_idx, mock_split, guides_dir, tmp_path):
        """Stale manifest → re-embed and upsert into Pinecone."""
        cache_dir = tmp_path / "cache"

        mock_embeddings = MagicMock()
        mock_embeddings.embed_documents.return_value = [[0.1] * 1536]
        mock_get_emb.return_value = mock_embeddings

        mock_index = MagicMock()
        mock_get_idx.return_value = mock_index

        mock_split.return_value = [
            Document(page_content="Test chunk", metadata={"source": "test.md"}),
        ]

        with patch("src.rag.indexer.CACHE_DIR", cache_dir), \
             patch("src.rag.indexer.MANIFEST_PATH", cache_dir / "manifest.json"):
            result = build_index(guides_dir)

        mock_index.delete.assert_called_once_with(delete_all=True, namespace=NAMESPACE)
        mock_index.upsert.assert_called_once()
        assert result == (mock_index, mock_embeddings)

    @patch("src.rag.indexer._get_pinecone_index")
    @patch("src.rag.indexer._get_embeddings")
    def test_skips_reembed_when_fresh(self, mock_get_emb, mock_get_idx, guides_dir, tmp_path):
        """Fresh manifest → return index without re-upserting."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        manifest_path = cache_dir / "manifest.json"
        manifest_path.write_text(json.dumps(_compute_manifest(guides_dir)))

        mock_embeddings = MagicMock()
        mock_get_emb.return_value = mock_embeddings

        mock_index = MagicMock()
        mock_get_idx.return_value = mock_index

        with patch("src.rag.indexer.CACHE_DIR", cache_dir), \
             patch("src.rag.indexer.MANIFEST_PATH", manifest_path):
            result = build_index(guides_dir)

        mock_index.upsert.assert_not_called()
        mock_index.delete.assert_not_called()
        assert result == (mock_index, mock_embeddings)
