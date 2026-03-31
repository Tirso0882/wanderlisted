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
    _load_and_chunk,
    build_index,
    NAMESPACE,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def guides_dir(tmp_path):
    """Create a temp directory with two small markdown guides."""
    d = tmp_path / "guides"
    d.mkdir()
    # Use Wikivoyage-style bare-text headings with enough content per section
    (d / "japan_guide.md").write_text(
        "# Japan Travel Guide\n\nJapan is a fascinating country in East Asia.\n\n"
        "Understand\nJapan has a rich history and culture spanning thousands of years. "
        "The country seamlessly blends ancient traditions with cutting-edge modern technology. "
        "From the bustling streets of Tokyo to the serene temples of Kyoto, "
        "Japan offers an incredible variety of experiences for every traveller.\n\n"
        "See\nVisit the spectacular temples in Kyoto, including Kinkaku-ji and Fushimi Inari. "
        "The cherry blossoms in spring are an unforgettable sight. "
        "Tokyo Tower and Senso-ji temple are must-visit landmarks in the capital city. "
        "Mount Fuji dominates the landscape and is visible on clear days from Tokyo.\n\n"
        "Eat\nTry sushi at Tsukiji outer market, ramen in a late-night shop, and tempura. "
        "Street food vendors sell takoyaki, yakitori, and okonomiyaki near train stations. "
        "Convenience stores like 7-Eleven and Lawson have surprisingly good food at low prices.\n"
    )
    (d / "france_guide.md").write_text(
        "# France Travel Guide\n\nFrance is known for art, wine, and cuisine.\n\n"
        "Understand\nFrance has a long and rich history stretching back millennia. "
        "French culture has influenced art, philosophy, and literature around the world. "
        "The country is famous for its contributions to gastronomy, fashion, and cinema. "
        "Paris has been the cultural capital of Europe for centuries.\n\n"
        "See\nVisit the Eiffel Tower and the Louvre Museum in Paris. "
        "The French Riviera offers beautiful Mediterranean beaches and glamorous resorts. "
        "Mont Saint-Michel is a stunning island commune in Normandy. "
        "The Loire Valley has hundreds of magnificent Renaissance chateaux.\n\n"
        "Eat\nFrench cuisine is world-renowned and varies by region. "
        "Try croissants and fresh baguettes from local boulangeries. "
        "Wine regions like Bordeaux and Burgundy offer excellent tastings. "
        "Don't miss the incredible cheese selection available at every market.\n"
    )
    return d


@pytest.fixture
def large_guide_dir(tmp_path):
    """Create a temp directory with one large markdown file with real sections."""
    d = tmp_path / "guides"
    d.mkdir()
    sections = []
    section_names = ["Understand", "Get in", "Get around", "See", "Do",
                     "Buy", "Eat", "Drink", "Sleep", "Stay safe"]
    for name in section_names:
        content = (
            f"This is a detailed travel guide section about {name.lower()}. "
            f"There are many things to know about this topic. "
            f"Visitors should plan ahead and research carefully. " * 5
        )
        sections.append(f"{name}\n{content}\n")
    (d / "big_guide.md").write_text(
        "# Big Destination Guide\n\nA comprehensive guide.\n\n"
        + "\n".join(sections)
    )
    return d


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


# ── _load_and_chunk ──────────────────────────────────────────────────────

class TestLoadAndChunk:
    def test_produces_chunks_with_metadata(self, guides_dir):
        """Section-level chunking should produce documents with source metadata."""
        docs = _load_and_chunk(guides_dir)
        assert len(docs) >= 2  # At least one chunk per file
        assert all(d.metadata["source"].endswith(".md") for d in docs)

    def test_large_doc_is_chunked(self, large_guide_dir):
        """Large docs should be split into multiple chunks."""
        docs = _load_and_chunk(large_guide_dir)
        assert len(docs) > 1
        assert all(d.metadata["source"] == "big_guide.md" for d in docs)

    def test_empty_dir_returns_empty(self, tmp_path):
        """Empty directory → no documents."""
        d = tmp_path / "empty"
        d.mkdir()
        assert _load_and_chunk(d) == []

    def test_metadata_includes_source(self, guides_dir):
        docs = _load_and_chunk(guides_dir)
        sources = {d.metadata["source"] for d in docs}
        assert "japan_guide.md" in sources
        assert "france_guide.md" in sources

    def test_metadata_includes_destination(self, guides_dir):
        """Each chunk should have a destination derived from filename."""
        docs = _load_and_chunk(guides_dir)
        destinations = {d.metadata.get("destination") for d in docs}
        assert "Japan Guide" in destinations or any("Japan" in d for d in destinations)

    def test_metadata_includes_section(self, guides_dir):
        """Section-level chunks should have section names."""
        docs = _load_and_chunk(guides_dir)
        sections = {d.metadata.get("section", "") for d in docs}
        # At least some recognised sections
        assert len(sections) > 1


# ── build_index ──────────────────────────────────────────────────────────

class TestBuildIndex:
    def test_returns_none_when_no_guides(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert build_index(d) is None

    @patch("src.rag.indexer._load_and_chunk")
    @patch("src.rag.indexer._get_pinecone_index")
    @patch("src.rag.indexer._get_embedding_generator")
    def test_builds_index_when_stale(self, mock_get_emb, mock_get_idx, mock_chunk, guides_dir, tmp_path):
        """Stale manifest → re-chunk, re-embed and upsert into Pinecone."""
        cache_dir = tmp_path / "cache"

        mock_emb_gen = MagicMock()
        mock_emb_gen.config.dimensions = 3072
        mock_emb_gen.config.batch_size = 100
        mock_emb_gen.embed_documents.return_value = [[0.1] * 3072]
        mock_get_emb.return_value = mock_emb_gen

        mock_index = MagicMock()
        mock_get_idx.return_value = mock_index

        mock_chunk.return_value = [
            Document(page_content="Test chunk", metadata={"source": "test.md", "destination": "Test", "section": "intro"}),
        ]

        with patch("src.rag.indexer.CACHE_DIR", cache_dir), \
             patch("src.rag.indexer.MANIFEST_PATH", cache_dir / "manifest.json"):
            result = build_index(guides_dir)

        mock_index.delete.assert_called_once_with(delete_all=True, namespace=NAMESPACE)
        mock_index.upsert.assert_called_once()
        assert result == (mock_index, mock_emb_gen)

    @patch("src.rag.indexer._get_pinecone_index")
    @patch("src.rag.indexer._get_embedding_generator")
    def test_skips_reembed_when_fresh(self, mock_get_emb, mock_get_idx, guides_dir, tmp_path):
        """Fresh manifest → return index without re-upserting."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        manifest_path = cache_dir / "manifest.json"
        manifest_path.write_text(json.dumps(_compute_manifest(guides_dir)))

        mock_emb_gen = MagicMock()
        mock_emb_gen.config.dimensions = 3072
        mock_get_emb.return_value = mock_emb_gen

        mock_index = MagicMock()
        mock_get_idx.return_value = mock_index

        with patch("src.rag.indexer.CACHE_DIR", cache_dir), \
             patch("src.rag.indexer.MANIFEST_PATH", manifest_path):
            result = build_index(guides_dir)

        mock_index.upsert.assert_not_called()
        mock_index.delete.assert_not_called()
        assert result == (mock_index, mock_emb_gen)
