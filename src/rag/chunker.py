"""Travel-domain document chunker for Pinecone / RAG indexing.

Implements a two-tier chunking strategy:

1. **Section-level** (primary) — splits on Wikivoyage bare-text headings
   (``Eat``, ``Sleep``, ``Get around`` …) with sub-splitting for oversized
   sections and merging for tiny ones.
2. **Recursive character** (fallback) — ``RecursiveCharacterTextSplitter``
   for documents without recognisable section headings (e.g. future PDFs).

Each chunk is enriched with lightweight metadata for Pinecone filtering:
``destination``, ``section``, ``chunk_position``, ``content_type``.
"""

import re
import time
from typing import Any, Optional, Union

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from custom_logging import AppLogger, log_function_call

# ── Wikivoyage section names ───────────────────────────────────────────
SECTION_NAMES: set[str] = {
    "Understand", "Get in", "Get around", "See", "Do", "Buy", "Eat",
    "Drink", "Sleep", "Stay safe", "Stay healthy", "Connect", "Cope",
    "Go next", "Respect", "Talk", "Learn", "Work",
    # Sub-sections common in Wikivoyage
    "Budget", "Mid-range", "Splurge",
    "By plane", "By train", "By bus", "By car", "By boat",
    "By taxi", "By metro", "By bicycle",
}

_SECTION_PAT = re.compile(
    r"^(" + "|".join(re.escape(n) for n in sorted(SECTION_NAMES, key=len, reverse=True)) + r")\s*$",
    re.MULTILINE,
)

# ── Travel-domain topic keywords (for content_type classification) ──────
_TRAVEL_TOPICS: dict[str, list[str]] = {
    "food_and_drink": ["restaurant", "cuisine", "dish", "food", "eat", "drink",
                       "café", "bar", "street food", "market"],
    "accommodation": ["hotel", "hostel", "guesthouse", "airbnb", "sleep",
                      "budget", "mid-range", "splurge", "booking"],
    "transportation": ["bus", "train", "metro", "taxi", "airport", "flight",
                       "ferry", "bicycle", "get around", "bts", "skytrain"],
    "sightseeing": ["temple", "museum", "palace", "monument", "park",
                    "landmark", "cathedral", "ruins", "gallery"],
    "practical": ["visa", "currency", "safety", "scam", "embassy",
                  "insurance", "sim card", "wifi", "connect", "cope"],
    "culture": ["etiquette", "custom", "festival", "language", "respect",
                "tradition", "religion", "dress code"],
}


class DocumentChunker:
    """Travel-domain chunker with section-level splitting and recursive fallback.

    Attributes:
        default_chunk_size: Max chars per chunk when using recursive splitting.
        default_chunk_overlap: Overlap between recursive chunks.
        min_chunk_size: Chunks smaller than this are merged into neighbours.
        max_section_size: Sections larger than this are sub-split at paragraphs.
    """

    def __init__(
        self,
        logger_name: str = "rag.chunker",
        default_chunk_size: int | None = None,
        default_chunk_overlap: int | None = None,
        min_chunk_size: int | None = None,
        max_section_size: int | None = None,
    ) -> None:
        import config as app_config

        if default_chunk_size is None:
            default_chunk_size = app_config.get("rag", "chunk_size", 2000)
        if default_chunk_overlap is None:
            default_chunk_overlap = app_config.get("rag", "chunk_overlap", 200)
        if min_chunk_size is None:
            min_chunk_size = app_config.get("rag", "min_chunk_size", 200)
        if max_section_size is None:
            max_section_size = app_config.get("rag", "max_section_size", 3000)

        if default_chunk_size <= 0:
            raise ValueError("default_chunk_size must be positive")
        if default_chunk_overlap < 0:
            raise ValueError("default_chunk_overlap cannot be negative")
        if default_chunk_overlap >= default_chunk_size:
            raise ValueError("default_chunk_overlap must be less than default_chunk_size")

        self.logger = AppLogger(logger_name=logger_name, level="DEBUG")
        self.default_chunk_size = default_chunk_size
        self.default_chunk_overlap = default_chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_section_size = max_section_size
        self.logger.info(
            f"DocumentChunker initialised — chunk_size={default_chunk_size}, "
            f"overlap={default_chunk_overlap}, min={min_chunk_size}, max_section={max_section_size}"
        )

    # ── Public API ───────────────────────────────────────────────────────

    @log_function_call
    def chunk_documents(
        self,
        documents: Union[str, Document, list[Document]],
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> list[Document]:
        """Split documents into retrieval-ready chunks with travel metadata.

        Tries section-level splitting first; falls back to markdown-header
        then recursive-character splitting when section headings aren't found.
        """
        chunk_size = chunk_size or self.default_chunk_size
        chunk_overlap = chunk_overlap or self.default_chunk_overlap

        docs = self._normalise_input(documents)
        if not docs:
            self.logger.warning("No content to chunk")
            return []

        all_chunks: list[Document] = []
        for doc in docs:
            chunks = self._chunk_single(doc, chunk_size, chunk_overlap)
            all_chunks.extend(chunks)

        self.logger.info(f"Produced {len(all_chunks)} chunks from {len(docs)} document(s)")
        return all_chunks

    # ── Internal: per-document chunking ──────────────────────────────────

    def _chunk_single(
        self, doc: Document, chunk_size: int, chunk_overlap: int,
    ) -> list[Document]:
        """Choose the best strategy for a single document.

        **Hierarchy rationale (domain-aware, not generic):**
        1. Section-level first — most specific for Wikivoyage structure (bare "Eat", "Sleep" headings).
           Best retrieval (100% Hits@1), cohesive chunks, zero cost. Eval-proven.
        2. Markdown-header fallback — for docs with # ## ### structure (blogs, docs).
           Also cheap, catches documents that markdown-structured.
        3. Recursive fallback — generic character splitting for unstructured text (PDFs, transcripts).
           Most general, handles any input, but creates more noise.

        See docs/CHUNKING_STRATEGY_RATIONALE.md for full analysis.
        """
        text = doc.page_content
        source = doc.metadata.get("source", "unknown")
        destination = self._extract_destination(source)

        # Strategy 1: Section-level (Wikivoyage guides)
        sections = self._split_on_sections(text)
        if len(sections) > 1:
            self.logger.debug(f"  {source}: section-level → {len(sections)} raw sections")
            chunks = self._build_section_chunks(sections, doc.metadata, destination)
            if chunks:
                return chunks

        # Strategy 2: Markdown header splitting
        md_chunks = self._split_on_markdown_headers(text, doc.metadata, destination)
        if len(md_chunks) > 1:
            self.logger.debug(f"  {source}: markdown-header → {len(md_chunks)} chunks")
            return md_chunks

        # Strategy 3: Recursive character splitting (fallback / PDFs)
        self.logger.debug(f"  {source}: recursive fallback")
        return self._split_recursive(text, doc.metadata, destination, chunk_size, chunk_overlap)

    # ── Section-level splitting ──────────────────────────────────────────

    def _split_on_sections(self, text: str) -> list[tuple[str, str]]:
        """Return ``[(section_name, section_text), …]`` using Wikivoyage headings."""
        lines = text.split("\n")
        sections: list[tuple[str, str]] = []
        current_name = "intro"
        current_lines: list[str] = []

        for line in lines:
            m = _SECTION_PAT.match(line)
            if m:
                if current_lines:
                    sections.append((current_name, "\n".join(current_lines).strip()))
                current_name = m.group(1)
                current_lines = [line]
            else:
                current_lines.append(line)
        if current_lines:
            sections.append((current_name, "\n".join(current_lines).strip()))

        return sections

    def _build_section_chunks(
        self,
        sections: list[tuple[str, str]],
        base_meta: dict,
        destination: str,
    ) -> list[Document]:
        """Merge small sections, sub-split large ones, attach metadata."""
        # Merge + sub-split
        merged: list[tuple[str, str]] = []
        buf_name, buf_text = "", ""
        for name, text in sections:
            if not text:
                continue
            if buf_text:
                buf_text = buf_text + "\n\n" + text
                buf_name = buf_name or name
            else:
                buf_name, buf_text = name, text

            if len(buf_text) >= self.min_chunk_size:
                merged.append((buf_name, buf_text))
                buf_name, buf_text = "", ""

        if buf_text:
            if merged:
                prev_name, prev_text = merged[-1]
                merged[-1] = (prev_name, prev_text + "\n\n" + buf_text)
            else:
                merged.append((buf_name, buf_text))

        # Sub-split oversized sections at paragraph boundaries
        final: list[tuple[str, str]] = []
        for name, text in merged:
            if len(text) <= self.max_section_size:
                final.append((name, text))
            else:
                parts = self._subsplit_at_paragraphs(text, self.max_section_size)
                for i, part in enumerate(parts):
                    final.append((f"{name} ({i+1})" if len(parts) > 1 else name, part))

        # Build Document objects with metadata
        chunks: list[Document] = []
        total = len(final)
        for idx, (section_name, section_text) in enumerate(final):
            meta = self._make_chunk_metadata(
                base_meta=base_meta,
                destination=destination,
                section=section_name,
                chunk_index=idx,
                total_chunks=total,
                chunk_method="section",
                content=section_text,
            )
            chunks.append(Document(page_content=section_text, metadata=meta))
        return chunks

    # ── Markdown header splitting ────────────────────────────────────────

    def _split_on_markdown_headers(
        self, text: str, base_meta: dict, destination: str,
    ) -> list[Document]:
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
            ("####", "Header 4"),
            ("#####", "Header 5"),
            ("######", "Header 6"),
        ]
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False,
            return_each_line=False,
        )
        splits = splitter.split_text(text)
        valid = [s for s in splits if len(s.page_content) >= self.min_chunk_size]
        if len(valid) <= 1:
            return []

        chunks: list[Document] = []
        total = len(valid)
        for idx, split in enumerate(valid):
            section = (
                split.metadata.get("Header 2")
                or split.metadata.get("Header 1")
                or f"section_{idx}"
            )
            meta = self._make_chunk_metadata(
                base_meta=base_meta,
                destination=destination,
                section=section,
                chunk_index=idx,
                total_chunks=total,
                chunk_method="markdown_header",
                content=split.page_content,
            )
            chunks.append(Document(page_content=split.page_content, metadata=meta))
        return chunks

    # ── Recursive character splitting ────────────────────────────────────

    def _split_recursive(
        self,
        text: str,
        base_meta: dict,
        destination: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[Document]:
        separators = ["\n\n", "\n", ". ", ", ", " ", ""]
        splitter = RecursiveCharacterTextSplitter(
            separators=separators,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        raw = splitter.create_documents([text], [base_meta])

        chunks: list[Document] = []
        total = len(raw)
        for idx, doc in enumerate(raw):
            meta = self._make_chunk_metadata(
                base_meta=base_meta,
                destination=destination,
                section=f"part_{idx+1}",
                chunk_index=idx,
                total_chunks=total,
                chunk_method="recursive",
                content=doc.page_content,
            )
            chunks.append(Document(page_content=doc.page_content, metadata=meta))
        return chunks

    # ── Metadata helpers ─────────────────────────────────────────────────

    def _make_chunk_metadata(
        self,
        base_meta: dict,
        destination: str,
        section: str,
        chunk_index: int,
        total_chunks: int,
        chunk_method: str,
        content: str,
    ) -> dict[str, Any]:
        """Build lean Pinecone-ready metadata for a single chunk."""
        return {
            "source": base_meta.get("source", "unknown"),
            "destination": destination,
            "section": section,
            "chunk_index": chunk_index,
            "chunk_position": f"{chunk_index + 1}/{total_chunks}",
            "chunk_method": chunk_method,
            "chunk_length": len(content),
            "content_type": self._classify_travel_content(content),
            "processing_timestamp": int(time.time()),
        }

    @staticmethod
    def _classify_travel_content(text: str) -> str:
        """Classify chunk into a travel-domain content type."""
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for topic, keywords in _TRAVEL_TOPICS.items():
            scores[topic] = sum(1 for kw in keywords if kw in text_lower)
        if not scores or max(scores.values()) == 0:
            return "general"
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    @staticmethod
    def _extract_destination(source: str) -> str:
        """Derive destination name from filename like ``bangkok.md``."""
        name = source.replace(".md", "").replace("_", " ")
        return name.title() if name else "unknown"

    # ── Utility ──────────────────────────────────────────────────────────

    @staticmethod
    def _subsplit_at_paragraphs(text: str, max_chars: int) -> list[str]:
        """Break *text* into ≤ *max_chars* pieces at paragraph boundaries."""
        paragraphs = text.split("\n\n")
        parts: list[str] = []
        current = ""
        for para in paragraphs:
            candidate = (current + "\n\n" + para).strip() if current else para.strip()
            if len(candidate) > max_chars and current:
                parts.append(current.strip())
                current = para.strip()
            else:
                current = candidate
        if current.strip():
            parts.append(current.strip())
        return parts

    @staticmethod
    def _normalise_input(documents: Union[str, Document, list[Document]]) -> list[Document]:
        """Accept str, single Document, or list and return a list."""
        if isinstance(documents, str):
            return [Document(page_content=documents, metadata={})]
        if isinstance(documents, Document):
            return [documents]
        if isinstance(documents, list):
            return documents
        raise TypeError(f"Unsupported input type: {type(documents)}")
