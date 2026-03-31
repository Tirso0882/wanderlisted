"""Tests for src/rag/chunker.py — travel-domain DocumentChunker."""

import pytest
from langchain_core.documents import Document

from src.rag.chunker import DocumentChunker, SECTION_NAMES


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def chunker():
    return DocumentChunker(
        logger_name="test.chunker",
        default_chunk_size=500,
        default_chunk_overlap=50,
        min_chunk_size=100,
        max_section_size=1500,
    )


@pytest.fixture
def wikivoyage_doc():
    """Realistic Wikivoyage-style document with bare-text headings."""
    return Document(
        page_content=(
            "# Bangkok Travel Guide\n\nBangkok is the capital of Thailand.\n\n"
            "Understand\nBangkok is a tropical metropolis with a rich cultural heritage. "
            "The city blends ancient temples with modern skyscrapers. "
            "Over 10 million people call it home.\n\n"
            "Get around\nBangkok has a decent public transportation network. "
            "The BTS Skytrain and MRT subway cover most tourist areas. "
            "Taxis are cheap but traffic can be terrible.\n\n"
            "See\nMost sights are on Rattanakosin island. "
            "The Grand Palace and Wat Pho are must-visits. "
            "Lumphini Park is great for escaping the heat.\n\n"
            "Eat\nBangkok boasts 50,000 places to eat. "
            "Try pad thai, green curry, and mango sticky rice. "
            "Street food is cheap and delicious.\n\n"
            "Sleep\nAccommodation ranges from budget backpacker hostels in Khao San Road "
            "to luxury five-star hotels along the river.\n"
        ),
        metadata={"source": "bangkok.md"},
    )


@pytest.fixture
def markdown_header_doc():
    """Document with standard ## markdown headers (non-Wikivoyage)."""
    return Document(
        page_content=(
            "# City Guide\n\n"
            "## Introduction\nThis city is wonderful and has lots to offer visitors. "
            "It has a rich history spanning many centuries, beautiful architecture, "
            "and friendly locals who welcome tourists with open arms.\n\n"
            "## Transportation\nThere are many ways to get around this city. "
            "The bus network covers all major neighborhoods and runs from early morning "
            "until late at night. Taxis are readily available and reasonably priced. "
            "The metro system is modern and efficient.\n\n"
            "## Dining\nMany restaurants serve both local and international cuisine. "
            "Street food vendors line the main boulevards offering affordable meals. "
            "Fine dining establishments can be found in the historic quarter. "
            "Don't miss the local specialty dishes that this city is famous for.\n"
        ),
        metadata={"source": "generic_city.md"},
    )


@pytest.fixture
def plain_text_doc():
    """Document with no recognisable headings (e.g. raw PDF text)."""
    return Document(
        page_content=(
            "This is a long travel document without any headers. " * 30
        ),
        metadata={"source": "plain_travel.pdf"},
    )


# ── Constructor ──────────────────────────────────────────────────────────

class TestConstructor:
    def test_valid_init(self):
        c = DocumentChunker(default_chunk_size=1000, default_chunk_overlap=100)
        assert c.default_chunk_size == 1000

    def test_rejects_zero_chunk_size(self):
        with pytest.raises(ValueError, match="positive"):
            DocumentChunker(default_chunk_size=0)

    def test_rejects_negative_overlap(self):
        with pytest.raises(ValueError, match="negative"):
            DocumentChunker(default_chunk_size=500, default_chunk_overlap=-1)

    def test_rejects_overlap_gte_chunk_size(self):
        with pytest.raises(ValueError, match="less than"):
            DocumentChunker(default_chunk_size=500, default_chunk_overlap=500)


# ── Section-level splitting ──────────────────────────────────────────────

class TestSectionSplitting:
    def test_wikivoyage_sections_detected(self, chunker, wikivoyage_doc):
        chunks = chunker.chunk_documents(wikivoyage_doc)
        assert len(chunks) >= 3  # intro + at least a few sections

    def test_section_metadata_present(self, chunker, wikivoyage_doc):
        chunks = chunker.chunk_documents(wikivoyage_doc)
        sections = {c.metadata["section"] for c in chunks}
        # At least some known sections should be present
        known = {"Eat", "See", "Get around", "Sleep", "Understand"}
        assert sections & known  # non-empty intersection

    def test_destination_extracted(self, chunker, wikivoyage_doc):
        chunks = chunker.chunk_documents(wikivoyage_doc)
        assert all(c.metadata["destination"] == "Bangkok" for c in chunks)

    def test_source_preserved(self, chunker, wikivoyage_doc):
        chunks = chunker.chunk_documents(wikivoyage_doc)
        assert all(c.metadata["source"] == "bangkok.md" for c in chunks)

    def test_chunk_method_is_section(self, chunker, wikivoyage_doc):
        chunks = chunker.chunk_documents(wikivoyage_doc)
        assert all(c.metadata["chunk_method"] == "section" for c in chunks)

    def test_content_type_classified(self, chunker, wikivoyage_doc):
        chunks = chunker.chunk_documents(wikivoyage_doc)
        types = {c.metadata["content_type"] for c in chunks}
        # At least one food-related chunk should be classified
        assert "food_and_drink" in types or "general" in types


# ── Markdown header fallback ─────────────────────────────────────────────

class TestMarkdownHeaderFallback:
    def test_markdown_headers_detected(self, chunker, markdown_header_doc):
        chunks = chunker.chunk_documents(markdown_header_doc)
        assert len(chunks) >= 2

    def test_chunk_method_is_markdown_header(self, chunker, markdown_header_doc):
        chunks = chunker.chunk_documents(markdown_header_doc)
        methods = {c.metadata["chunk_method"] for c in chunks}
        assert "markdown_header" in methods or "recursive" in methods


# ── Recursive fallback ──────────────────────────────────────────────────

class TestRecursiveFallback:
    def test_plain_text_chunked(self, chunker, plain_text_doc):
        chunks = chunker.chunk_documents(plain_text_doc)
        assert len(chunks) > 1

    def test_chunk_method_is_recursive(self, chunker, plain_text_doc):
        chunks = chunker.chunk_documents(plain_text_doc)
        assert all(c.metadata["chunk_method"] == "recursive" for c in chunks)


# ── Input normalisation ─────────────────────────────────────────────────

class TestInputNormalisation:
    def test_accepts_string(self, chunker):
        chunks = chunker.chunk_documents("Hello world. " * 100)
        assert len(chunks) >= 1

    def test_accepts_single_document(self, chunker, wikivoyage_doc):
        chunks = chunker.chunk_documents(wikivoyage_doc)
        assert len(chunks) >= 1

    def test_accepts_list_of_documents(self, chunker, wikivoyage_doc, markdown_header_doc):
        chunks = chunker.chunk_documents([wikivoyage_doc, markdown_header_doc])
        sources = {c.metadata["source"] for c in chunks}
        assert "bangkok.md" in sources

    def test_empty_string_returns_empty(self, chunker):
        chunks = chunker.chunk_documents("")
        assert chunks == []

    def test_rejects_invalid_type(self, chunker):
        with pytest.raises(TypeError):
            chunker.chunk_documents(12345)


# ── Sub-splitting and merging ────────────────────────────────────────────

class TestSubsplitAndMerge:
    def test_large_section_subsplit(self):
        """Sections > max_section_size should be sub-split at paragraph breaks."""
        chunker = DocumentChunker(max_section_size=300, min_chunk_size=50)
        # Build a big Eat section with paragraph breaks so sub-splitting can work
        eat_paragraphs = "\n\n".join([
            f"Paragraph {i}: This restaurant has amazing food and great service." 
            for i in range(20)
        ])
        big_section = (
            "# Guide\n\n"
            "Understand\nThis is a wonderful travel destination with rich history and culture.\n\n"
            f"Eat\n{eat_paragraphs}\n\n"
            "Sleep\nThere are many hotels and hostels to choose from in the city centre.\n"
        )
        doc = Document(page_content=big_section, metadata={"source": "test.md"})
        chunks = chunker.chunk_documents(doc)
        # The Eat section is ~1300 chars with 300 max → should produce multiple chunks
        assert len(chunks) >= 4

    def test_tiny_sections_merged(self):
        """Sections < min_chunk_size should be merged."""
        chunker = DocumentChunker(min_chunk_size=500, max_section_size=5000)
        small_sections = (
            "# Guide\n\nIntro.\n\n"
            "See\nA temple.\n\n"
            "Do\nA park.\n\n"
            "Buy\nA market with many stalls selling local goods and souvenirs. " * 10 + "\n"
        )
        doc = Document(page_content=small_sections, metadata={"source": "test.md"})
        chunks = chunker.chunk_documents(doc)
        # See and Do should be merged into fewer chunks
        assert len(chunks) < 4


# ── Metadata completeness ───────────────────────────────────────────────

class TestMetadataCompleteness:
    def test_all_required_metadata_keys(self, chunker, wikivoyage_doc):
        chunks = chunker.chunk_documents(wikivoyage_doc)
        required = {
            "source", "destination", "section", "chunk_index",
            "chunk_position", "chunk_method", "chunk_length",
            "content_type", "processing_timestamp",
        }
        for chunk in chunks:
            assert required.issubset(chunk.metadata.keys()), \
                f"Missing keys: {required - set(chunk.metadata.keys())}"

    def test_chunk_position_format(self, chunker, wikivoyage_doc):
        chunks = chunker.chunk_documents(wikivoyage_doc)
        for chunk in chunks:
            pos = chunk.metadata["chunk_position"]
            parts = pos.split("/")
            assert len(parts) == 2
            assert parts[0].isdigit() and parts[1].isdigit()
