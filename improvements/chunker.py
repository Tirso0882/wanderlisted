"""
Document chunking module for Azure AI Search integration.

This module provides advanced document chunking functionality optimised for financial documents
and Azure AI Search integration. It implements semantic chunking strategies using markdown
headers and recursive character splitting with metadata for better
retrieval performance.

The module is designed specifically for the Financial Knowledge Assistant RAG system,
providing enhanced metadata for Azure AI Search optimisation including content analysis,
page mapping, table detection, and financial metrics identification.

Example:

    ```python
    from document_processing.chunker import DocumentChunker

    chunker = DocumentChunker(
        logger_name="financial_chunker",
        default_chunk_size=2000,
        default_chunk_overlap=200
    )

    chunks = chunker.chunk_by_markdown_header(
        documents=processed_document,
        chunk_size=1500,
        chunk_overlap=150
    )

    for chunk in chunks:
        print(f"Chunk {chunk.metadata['chunk_idx']}: {chunk.metadata['content_type']}")
        print(f"Pages: {chunk.metadata['page_range']}")
        print(f"Financial metrics: {chunk.metadata['contains_financial_metrics']}")
    ```

Attributes:
    This module contains the DocumentChunker class which provides the main chunking functionality.

Note:
    This module requires the following dependencies:
    - langchain for document processing and text splitting
    - custom_logging for application logging
    - re for regular expression operations
    - time for timestamp generation

TODO:
    * Add support for additional document formats (Word, Excel)
    * Implement advanced NLP-based entity extraction

Author:
    Tirso Gomez

Version:
    1.0.0
"""

import re
import time
from typing import Any, Dict, List, Optional, Union

from langchain.docstore.document import Document
from langchain.text_splitter import (MarkdownHeaderTextSplitter,
                                     RecursiveCharacterTextSplitter)

from custom_logging import AppLogger, log_function_call


class DocumentChunker:
    """
    Advanced document chunker optimised for financial documents and Azure AI Search.
    
    The chunker supports multiple input formats and provides enhanced metadata
    including page mapping, content analysis, financial metrics detection,
    table summaries, and search optimisation fields.
    
    Attributes:
        logger (AppLogger): Logger instance for debugging and monitoring.
        default_chunk_size (int): Default maximum size of chunks in characters.
        default_chunk_overlap (int): Default overlap between chunks in characters.
    
    Note:
        The chunker is optimised for financial documents and includes specialised
        detection for financial metrics, tables, and structured data commonly
        found in corporate reports and financial statements.
    """

    def __init__(
        self,
        logger_name: str,
        default_chunk_size: Optional[int] = None,
        default_chunk_overlap: Optional[int] = None,
    ) -> None:
        """
        Initialize the document chunker with specified parameters.
        
        Args:
            logger_name: Name for the logger instance. Used for debugging and monitoring.
            default_chunk_size: Default maximum size of chunks in characters. Should be
                optimised for the target LLM's context window and retrieval performance.
            default_chunk_overlap: Default overlap between chunks in characters. Helps
                maintain context continuity across chunk boundaries.
        
        Raises:
            ValueError: If chunk_size or chunk_overlap are negative values.
        
        """
        if default_chunk_size <= 0:
            raise ValueError("default_chunk_size must be positive")
        if default_chunk_overlap < 0:
            raise ValueError("default_chunk_overlap cannot be negative")
        if default_chunk_overlap >= default_chunk_size:
            raise ValueError("default_chunk_overlap must be less than default_chunk_size")
            
        self.logger = AppLogger(logger_name=logger_name, level="DEBUG")
        self.default_chunk_size = default_chunk_size
        self.default_chunk_overlap = default_chunk_overlap
        self.logger.info(
            f"Document chunker initialized with default chunk size: {default_chunk_size}, "
            f"overlap: {default_chunk_overlap}"
        )

    @log_function_call
    def chunk_by_markdown_header(
        self,
        documents: Union[str, Document, List[Document], dict],
        headers_to_split_on: Optional[List[tuple]] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        min_chunk_size: int = 100,
        min_chunks_for_large_doc: int = 3,
        large_doc_threshold: int = 10000
    ) -> List[Document]:
        """
        Chunk documents using markdown headers with metadata.
        
        This method implements an intelligent chunking strategy that prioritises markdown
        header-based splitting for better semantic coherence. If header-based splitting
        fails or produces insufficient chunks, it falls back to recursive character
        splitting. Each chunk is enhanced with metadata optimised for Azure AI Search
        including page mapping, content analysis, and financial metrics.
        
        The method supports multiple input formats and automatically detects the best
        chunking strategy based on document structure and content characteristics.
        
        Args:
            documents: Document content in various formats:
                - str: Plain text content
                - Document: LangChain Document object with content and metadata
                - List[Document]: Multiple LangChain Documents to be concatenated
                - dict: Processed document result from Azure Document Intelligence
            headers_to_split_on: List of tuples defining markdown headers for splitting.
                Each tuple contains (header_marker, header_name). Defaults to standard
                markdown headers from # to ######.
            chunk_size: Maximum size of chunks in characters when fallback chunking is used.
                If None, uses default_chunk_size from initialization.
            chunk_overlap: Overlap between chunks in characters when fallback chunking is used.
                If None, uses default_chunk_overlap from initialization.
            min_chunk_size: Minimum size in characters for a chunk to be considered valid.
                Chunks smaller than this will be filtered out or merged.
            min_chunks_for_large_doc: Minimum number of chunks expected for large documents.
                Used to determine if chunking strategy should be adjusted.
            large_doc_threshold: Character count threshold for a document to be considered
                large and require special handling.
        
        Returns:
            List[Document]: List of chunked documents with enhanced metadata. Each document
                contains the chunk content and comprehensive metadata including:
                - chunk_idx: Index of the chunk (0-based)
                - chunk_method: Method used for chunking ("markdown_header" or "recursive_character")
                - page_numbers: List of page numbers the chunk spans
                - content_type: Classified content type (e.g., "tabular_data", "financial_data")
                - contains_financial_metrics: Boolean indicating presence of financial data
                - header_hierarchy: Dictionary of header levels and their content
                - primary_header, secondary_header, tertiary_header: Individual header levels for search
                - all_headers: Combined header text for search optimization
                - And many more fields optimised for Azure AI Search
        
        Raises:
            ValueError: If documents parameter is None or empty.
            TypeError: If documents parameter is not in a supported format.
        
        Note:
            - The method automatically detects document structure and chooses the optimal
              chunking strategy
            - For financial documents, it provides specialized metadata for financial
              metrics, tables, and structured data
            - Page mapping is automatically extracted from document content when available
            - Fallback strategies ensure chunking even for poorly structured documents
            
        Warning:
            Large documents (>10,000 characters) that result in only one chunk may indicate
            formatting issues or content that is not suitable for semantic chunking.
        """
        if headers_to_split_on is None:
            headers_to_split_on = [
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
                ("####", "Header 4"),
                ("#####", "Header 5"),
                ("######", "Header 6"),
            ]
        
        chunk_size = chunk_size or self.default_chunk_size
        chunk_overlap = chunk_overlap or self.default_chunk_overlap
        
        text, base_metadata = self._extract_text_and_metadata(documents)
        
        if not text:
            self.logger.warning("Document has no content to chunk")
            return []
        
        doc_length = len(text)
        self.logger.info(f"Chunking document by markdown headers, content length: {doc_length}")
        
        document_context = self._extract_document_context(base_metadata, text)
        
        page_mapping = self._extract_page_mapping(text)
        self.logger.info(f"Extracted page mapping with {len(page_mapping)} page positions")
        
        page_info = self._extract_page_info_from_metadata(base_metadata)
        
        header_count = 0
        for header_mark, _ in headers_to_split_on:
            header_count += text.count(f"\n{header_mark} ")
        
        self.logger.info(f"Document contains {header_count} potential markdown headers")
        
        try:
            text_splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=headers_to_split_on,
                strip_headers=False,
                return_each_line=False
            )
            
            md_splits = text_splitter.split_text(text)
            
            if len(md_splits) > 1:
                valid_splits = [split for split in md_splits if len(split.page_content) >= min_chunk_size]
                if len(valid_splits) > 1:
                    self.logger.info(f"Successfully split document into {len(valid_splits)} chunks using markdown headers")
                    result_chunks = []
                    for i, split in enumerate(valid_splits):
                        enhanced_metadata = self._create_enhanced_chunk_metadata(
                            base_metadata=base_metadata,
                            chunk_content=split.page_content,
                            chunk_index=i,
                            total_chunks=len(valid_splits),
                            chunk_method="markdown_header",
                            header_metadata=split.metadata,
                            document_context=document_context,
                            page_mapping=page_mapping,
                            page_info=page_info
                        )
                        
                        result_chunks.append(Document(page_content=split.page_content, metadata=enhanced_metadata))
                    
                    self.logger.info(f"Created {len(result_chunks)} chunks from document using markdown headers")
                    
                    # Ensure enough chunks for large documents
                    if doc_length > large_doc_threshold and len(result_chunks) < min_chunks_for_large_doc:
                        self.logger.warning(
                            f"Document is large ({doc_length} chars) but only created {len(result_chunks)} chunks. "
                            f"Falling back to recursive splitting."
                        )
                    else:
                        return result_chunks
                else:
                    self.logger.warning(f"Markdown header splitter created {len(md_splits)} chunks, but only {len(valid_splits)} are valid. Falling back to recursive splitting.")
            else:
                self.logger.warning("Markdown header splitter only created one chunk. Falling back to recursive splitting.")
                if header_count > 0:
                    self.logger.warning(f"Despite having {header_count} potential headers, header-based chunking failed. Checking header format...")
                    for header_mark, _ in headers_to_split_on:
                        count = text.count(f"\n{header_mark} ")
                        if count > 0:
                            self.logger.info(f"Found {count} instances of '{header_mark}' headers")
                            header_pattern = re.compile(f"(\n{re.escape(header_mark)} .+?)(\n|$)")
                            matches = header_pattern.findall(text[:5000])
                            if matches:
                                self.logger.info(f"Example headers: {matches[:3]}")
        except Exception as e:
            self.logger.warning(f"Error using markdown header splitter: {str(e)}. Falling back to recursive splitting.")
        
        # Fall back to recursive character splitting if header splitting didn't work well
        self.logger.info(f"Using recursive character text splitter with chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
        
        separators = ["\n# ", "\n## ", "\n### ", "\n#### ", "\n##### ", "\n###### ", "\n\n", "\n", ". ", ", ", " ", ""]
        
        recursive_splitter = RecursiveCharacterTextSplitter(
            separators=separators,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        
        chunks = recursive_splitter.create_documents([text], [base_metadata])
        
        if len(chunks) == 1 and doc_length > large_doc_threshold:
            self.logger.warning(f"Document is {doc_length} chars but RecursiveCharacterTextSplitter only created 1 chunk. Trying with smaller chunk size.")
            adjusted_chunk_size = min(chunk_size, 1000)
            recursive_splitter = RecursiveCharacterTextSplitter(
                separators=["\n\n", "\n", ". ", " ", ""],
                chunk_size=adjusted_chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
            )
            chunks = recursive_splitter.create_documents([text], [base_metadata])
            self.logger.info(f"Created {len(chunks)} chunks with adjusted chunk size {adjusted_chunk_size}")

        enhanced_chunks = []
        for i, chunk in enumerate(chunks):
            enhanced_metadata = self._create_enhanced_chunk_metadata(
                base_metadata=base_metadata,
                chunk_content=chunk.page_content,
                chunk_index=i,
                total_chunks=len(chunks),
                chunk_method="recursive_character",
                header_metadata={},
                document_context=document_context,
                page_mapping=page_mapping,
                page_info=page_info
            )
            
            enhanced_chunks.append(Document(page_content=chunk.page_content, metadata=enhanced_metadata))
        
        self.logger.info(f"Created {len(enhanced_chunks)} chunks using recursive character splitting")
        
        if len(enhanced_chunks) == 1 and doc_length > large_doc_threshold:
            self.logger.warning(f"WARNING: Document is {doc_length} chars but only created 1 chunk. Content may be improperly formatted or not suitable for chunking.")
        
        return enhanced_chunks

    def _extract_page_mapping(self, text: str) -> Dict[int, int]:
        """
        Extract page mapping from document content using various detection strategies.
        
        This method analyzes document content to create a mapping between character
        positions and page numbers. It employs multiple strategies to detect page
        boundaries, including PageBreak markers, PageNumber annotations, and content-based
        estimation for documents without explicit page markers.
        
        The page mapping is crucial for accurate chunk-to-page assignment and enables
        users to reference specific pages when retrieving information from chunks.
        
        Args:
            text: Complete document text content to analyze for page boundaries.
        
        Returns:
            Dict[int, int]: Dictionary mapping character positions to page numbers.
                Keys are character positions (0-based) where pages start, values are
                page numbers (1-based). For example: {0: 1, 2000: 2, 4000: 3}
        
        Example:
            ```python
            text = "Content page 1\\n<!-- PageBreak -->\\nContent page 2"
            page_mapping = chunker._extract_page_mapping(text)
            # Returns: {0: 1, 25: 2}
            ```
        
        Note:
            The method uses the following detection strategies in order of preference:
            1. PageBreak markers (<!-- PageBreak -->)
            2. PageNumber annotations (<!-- PageNumber="N" -->)
            3. Content length estimation (fallback for unmarked documents)
            
            For documents without explicit page markers, the method estimates pages
            based on typical page length (~2000 characters per page).
        """
        page_mapping = {}
        current_page = 1
        
        # Strategy 1: Find PageBreak markers
        page_break_pattern = r'<!-- PageBreak -->'
        page_breaks = []
        
        for match in re.finditer(page_break_pattern, text):
            page_breaks.append(match.start())
        
        if page_breaks:
            self.logger.info(f"Found {len(page_breaks)} PageBreak markers")
            # Content before first page break is page 1
            page_mapping[0] = 1
            
            # Each page break marks the start of the next page
            for i, break_pos in enumerate(page_breaks):
                page_mapping[break_pos] = i + 2  # Next page after the break
        else:
            # Strategy 2: Look for PageNumber markers
            page_number_pattern = r'<!-- PageNumber="(\d+)" -->'
            page_numbers = []
            
            for match in re.finditer(page_number_pattern, text):
                page_num = int(match.group(1))
                page_numbers.append((match.start(), page_num))
            
            if page_numbers:
                self.logger.info(f"Found {len(page_numbers)} PageNumber markers")
                page_mapping[0] = 1
                
                for pos, page_num in page_numbers:
                    page_mapping[pos] = page_num
            else:
                # Strategy 3: Estimate pages based on content length
                self.logger.warning("No page break or page number markers found, estimating pages based on content length")
                
                # Estimate pages based on typical page length (assume ~2000 chars per page)
                estimated_page_length = 2000
                estimated_pages = max(1, len(text) // estimated_page_length)
                
                if estimated_pages > 1:
                    for i in range(estimated_pages):
                        page_start = i * estimated_page_length
                        page_mapping[page_start] = i + 1
                    self.logger.info(f"Estimated {estimated_pages} pages based on content length")
                else:
                    page_mapping[0] = 1
                    self.logger.info("Treating as single page document")
        
        self.logger.info(f"Created page mapping with {len(page_mapping)} page positions")
        return page_mapping

    def _determine_chunk_pages(self, chunk_content: str, text: str, page_mapping: Dict[int, int]) -> List[int]:
        """
        Determine which pages a chunk spans based on its position in the document.
        
        This method uses multiple strategies to accurately determine which pages a chunk
        spans by analyzing the chunk's position within the full document text. It employs
        sophisticated matching algorithms to handle various content formats and edge cases.
        
        The method is essential for providing accurate page references in chunk metadata,
        enabling users to locate the original source of information in the document.
        
        Args:
            chunk_content: Content of the specific chunk to locate within the document.
            text: Complete document text containing the chunk.
            page_mapping: Dictionary mapping character positions to page numbers,
                typically generated by _extract_page_mapping().
        
        Returns:
            List[int]: List of page numbers (1-based) that the chunk spans.
                For example: [2] for single page, [2, 3] for chunk spanning two pages.
                Returns [1] as fallback if position cannot be determined.
        
        Example:
            ```python
            chunk_content = "## Financial Results\\nRevenue increased by 15%"
            full_text = "# Report\\n...\\n## Financial Results\\nRevenue increased by 15%"
            page_mapping = {0: 1, 1000: 2}
            
            pages = chunker._determine_chunk_pages(chunk_content, full_text, page_mapping)
            # Returns: [2] if chunk is found on page 2
            ```
        
        Note:
            The method uses multiple detection strategies:
            1. Exact content matching
            2. Line-by-line matching for markdown content
            3. Normalized content matching (removing formatting)
            4. Distinctive phrase matching
            5. Content-based inference for special sections
            
            If position detection fails, the method provides intelligent fallbacks
            based on content type (e.g., executive summary → page 1, conclusion → last page).
        
        Warning:
            For chunks that cannot be precisely located, the method logs warnings
            and attempts intelligent estimation based on content characteristics.
        """
        clean_chunk = chunk_content.strip()
        
        chunk_start = -1
        
        # Strategy 1: Direct exact match
        chunk_start = text.find(clean_chunk)
        if chunk_start != -1:
            self.logger.debug(f"Found chunk by exact match at position {chunk_start}")
        
        # Strategy 2: Find by individual lines (most reliable for markdown)
        if chunk_start == -1:
            lines = clean_chunk.split('\n')
            self.logger.debug(f"Trying to find chunk position for {len(lines)} lines")
            
            for i, line in enumerate(lines[:10]):
                clean_line = line.strip()
                if clean_line and len(clean_line) > 3:
                    self.logger.debug(f"Looking for line: '{clean_line}'")
                    
                    pos = text.find(clean_line)
                    if pos != -1:
                        chunk_start = pos
                        self.logger.debug(f"Found chunk by exact line '{clean_line}' at position {chunk_start}")
                        break
                    
                    normalized_line = ' '.join(clean_line.split())
                    normalized_text_lines = [' '.join(tl.split()) for tl in text.split('\n')]
                    
                    for j, norm_text_line in enumerate(normalized_text_lines):
                        if norm_text_line == normalized_line:
                            text_lines = text.split('\n')
                            if j < len(text_lines):
                                pos = text.find(text_lines[j])
                                if pos != -1:
                                    chunk_start = pos
                                    self.logger.debug(f"Found chunk by normalized line '{clean_line}' at position {chunk_start}")
                                    break
                    if chunk_start != -1:
                        break
                    
                    if clean_line.startswith('#'):
                        header_text = clean_line.lstrip('#').strip()
                        if header_text:
                            pos = text.find(header_text)
                            if pos != -1:
                                chunk_start = pos
                                self.logger.debug(f"Found chunk by header text '{header_text}' at position {chunk_start}")
                                break
        
        # Strategy 3: Try without extra whitespace, remove markdown formatting and normalize
        if chunk_start == -1:
            normalized_chunk = clean_chunk
            normalized_chunk = re.sub(r'#{1,6}\s*', '', normalized_chunk)  # Remove headers
            normalized_chunk = re.sub(r'<[^>]+>', '', normalized_chunk)  # Remove HTML
            normalized_chunk = re.sub(r'\s+', ' ', normalized_chunk).strip()
            
            normalized_text = re.sub(r'<[^>]+>', '', text)
            normalized_text = re.sub(r'\s+', ' ', normalized_text)
            
            pos = normalized_text.find(normalized_chunk[:100])
            if pos != -1:
                # Convert back to original text position (approximate)
                chunk_start = pos
                self.logger.debug(f"Found chunk by normalized content at position {chunk_start}")
        
        # Strategy 4: Find by distinctive content phrases (non-common words)
        if chunk_start == -1:
            words = re.findall(r'\b[A-Za-z]{4,}\b', clean_chunk)
            distinctive_words = []
            common_words = {'this', 'that', 'with', 'from', 'they', 'have', 'been', 'will', 'were', 'are', 'the', 'and', 'for', 'you', 'all', 'not', 'but', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'man', 'men', 'put', 'say', 'she', 'too', 'use'}
            
            for word in words:
                if word.lower() not in common_words and len(word) > 4:
                    distinctive_words.append(word)
                if len(distinctive_words) >= 3:
                    break
            
            if distinctive_words:
                for i in range(len(distinctive_words) - 1):
                    phrase = f"{distinctive_words[i]}.*{distinctive_words[i+1]}"
                    match = re.search(phrase, text, re.IGNORECASE | re.DOTALL)
                    if match:
                        chunk_start = match.start()
                        self.logger.debug(f"Found chunk by distinctive phrase '{phrase}' at position {chunk_start}")
                        break
        
        # Strategy 5: Use content-based inference if still not found
        if chunk_start == -1:
            self.logger.warning(f"Could not determine exact chunk position for content starting with: {clean_chunk[:50]}...")
            
            # Try to infer page based on content type and headers
            content_lower = clean_chunk.lower()
            
            # Look for specific content patterns
            if re.search(r'executive\s+summary', content_lower):
                return [1]  # Executive summary usually on first page
            elif re.search(r'table\s+of\s+contents', content_lower):
                return [1, 2]
            elif re.search(r'conclusion|summary|outlook', content_lower):
                # Conclusion usually on last page
                max_page = max(page_mapping.values()) if page_mapping else 1
                return [max_page]
            elif re.search(r'legal\s+disclaimer|disclaimer', content_lower):
                # Disclaimers often at the end
                max_page = max(page_mapping.values()) if page_mapping else 1
                return [max_page]
            elif re.search(r'management\s+board|letter\s+from', content_lower):
                return [1, 2]  # Management letters usually early in document
            else:
                return [1]  # Default to page 1
        
        chunk_end = chunk_start + len(clean_chunk)
        self.logger.debug(f"Found chunk at position {chunk_start}-{chunk_end}")
        
        # Determine which pages the chunk spans
        pages = set()
        sorted_positions = sorted(page_mapping.keys())
        
        for i, pos in enumerate(sorted_positions):
            page_num = page_mapping[pos]
            
            # Find the next page break to determine page end
            next_pos = sorted_positions[i + 1] if i + 1 < len(sorted_positions) else len(text)
            
            # Check if chunk overlaps with this page
            page_start = pos
            page_end = next_pos
            
            # If there's any overlap between chunk and page
            if not (chunk_end <= page_start or chunk_start >= page_end):
                pages.add(page_num)
                self.logger.debug(f"Chunk overlaps with page {page_num} (page range: {page_start}-{page_end})")

        if not pages:
            pages.add(1)
        
        return sorted(list(pages))

    def _extract_document_context(self, metadata: Dict[str, Any], text: str) -> Dict[str, Any]:
        """
        Extract document-level context information for metadata enhancement.
        
        This method analyses the entire document to extract contextual information
        that helps in understanding the document's characteristics, complexity, and
        content themes. This context is used to enhance individual chunk metadata
        and improve search and retrieval performance.
        
        Args:
            metadata: Base document metadata from processing pipeline containing
                document identification, structure, and processing information.
            text: Complete document text content to analyze for context extraction.
        
        Returns:
            Dict[str, Any]: Document context containing:
                - document_length: Total character count
                - estimated_reading_time: Reading time in minutes (~200 words/min)
                - language: Document language (default "en")
                - document_complexity: Complexity level ("low", "medium", "high")
                - content_themes: List of main content themes
                - financial_indicators: List of detected financial indicators
                - table_count: Number of tables in document
                - figure_count: Number of figures/charts in document
                - source_type: Document format type
                - original_filename: Source filename
                - total_pages: Number of pages
                - processing_model: Model used for document processing
        
        Example:
            ```python
            metadata = {"document_identification": {"original_filename": "report.pdf"}}
            text = "# Financial Report\\nRevenue increased 15%..."
            
            context = chunker._extract_document_context(metadata, text)
            ```
        
        Note:
            The context information is used to:
            - Enhance individual chunk metadata with document-level insights
            - Provide document classification for search filtering
            - Enable quality assessment and content ranking
            - Support analytics and reporting features
            
            Reading time is estimated at 200 words per minute, which is typical
            for technical and financial documents.
        """
        context = {
            "document_length": len(text),
            "estimated_reading_time": max(1, len(text.split()) // 200),  # ~200 words per minute
            "language": "en",
            "document_complexity": self._assess_document_complexity(text),
            "content_themes": self._extract_content_themes(text),
            "financial_indicators": self._detect_financial_indicators(text),
            "table_count": self._count_tables_in_text(text),
            "figure_count": self._count_figures_in_text(text)
        }

        if metadata:
            doc_identification = metadata.get("document_identification", {})
            context.update({
                "source_type": doc_identification.get("content_type", "unknown"),
                "original_filename": doc_identification.get("original_filename", "unknown"),
                "file_size_bytes": doc_identification.get("file_size_bytes"),
                "processing_model": metadata.get("processing_metadata", {}).get("model", "unknown")
            })
            
            doc_structure = metadata.get("document_structure", {})
            page_summary = doc_structure.get("page_summary", {})
            context.update({
                "total_pages": page_summary.get("page_count", 0),
                "page_dimensions": page_summary.get("page_dimensions"),
                "document_angle": page_summary.get("angle", 0)
            })
        
        return context

    def _create_enhanced_chunk_metadata(
        self,
        base_metadata: Dict[str, Any],
        chunk_content: str,
        chunk_index: int,
        total_chunks: int,
        chunk_method: str,
        header_metadata: Dict[str, Any],
        document_context: Dict[str, Any],
        page_mapping: Dict[int, int],
        page_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create metadata for a chunk optimised for Azure AI Search.
        
        This method generates extensive metadata for each chunk, including content analysis,
        page mapping, search optimization fields, and financial document-specific attributes.
        The metadata is specifically designed to enhance retrieval performance in Azure AI
        Search and provide rich context for the RAG system.
        
        The generated metadata includes over 30 fields covering content classification,
        search optimization, quality scoring, and document structure information.
        
        Args:
            base_metadata: Original document metadata from processing pipeline.
            chunk_content: Text content of the specific chunk.
            chunk_index: Zero-based index of the chunk within the document.
            total_chunks: Total number of chunks in the document.
            chunk_method: Method used for chunking ("markdown_header" or "recursive_character").
            header_metadata: Metadata extracted from markdown headers during splitting.
            document_context: Document-level context information including complexity and themes.
            page_mapping: Dictionary mapping character positions to page numbers.
            page_info: Additional page information from document metadata.
        
        Returns:
            Dict[str, Any]: Metadata dictionary containing:
                - Core identification: chunk_idx, chunk_method, chunk_length, etc.
                - Page information: page_numbers, page_range, primary_page
                - Content analysis: content_type, contains_financial_metrics, key_topics
                - Search optimization: primary_header, secondary_header, tertiary_header, all_headers, keywords, boost_score
                - Structure: header_hierarchy, section_path, table_summaries
                - Quality metrics: chunk_quality_score, information_density, readability_score
                - Azure AI Search fields: filter_categories, facet_fields
        
        Example:
            ```python
            metadata = chunker._create_enhanced_chunk_metadata(
                base_metadata={"document_id": "report_2024"},
                chunk_content="## Revenue Analysis\\nRevenue increased 15%...",
                chunk_index=2,
                total_chunks=10,
                chunk_method="markdown_header",
                header_metadata={"Header 2": "Revenue Analysis"},
                document_context={"document_complexity": "medium"},
                page_mapping={0: 1, 1000: 2},
                page_info={"total_pages": 5}
            )
            ``` 
        Note:
            The metadata is optimised for Azure AI Search and includes:
            - Faceted search fields for filtering and navigation
            - Boost scores for relevance ranking
            - Searchable text optimised for retrieval
            - Content classification for targeted search
            - Quality scores for result ranking
            
            Financial document-specific features include detection of:
            - Financial metrics and ratios
            - Table content and summaries
            - Key financial topics and entities
            - Structured data indicators
        
        Returns:
            The metadata dictionary contains all fields necessary for effective
            search, retrieval, and user experience in the RAG system.
        """
        chunk_length = len(chunk_content)
        chunk_word_count = len(chunk_content.split())
        
        enhanced_metadata = {
            "chunk_idx": chunk_index,
            "chunk_method": chunk_method,
            "chunk_length": chunk_length,
            "chunk_word_count": chunk_word_count,
            "chunk_position": f"{chunk_index + 1}/{total_chunks}",
            "relative_position": round((chunk_index + 1) / total_chunks, 3),
            "processing_timestamp": int(time.time())
        }
        
        enhanced_metadata.update(base_metadata)
        
        # Determine page numbers for this chunk
        full_text = ""
        if base_metadata and "content" in base_metadata:
            content_dict = base_metadata["content"]
            if isinstance(content_dict, dict):
                full_text = content_dict.get("markdown", "") or content_dict.get("text", "")
            elif isinstance(content_dict, str):
                full_text = content_dict

        chunk_pages = []
        if full_text and page_mapping:
            chunk_pages = self._determine_chunk_pages(chunk_content, full_text, page_mapping)
        
        if not chunk_pages or chunk_pages == [1]:
            total_pages = page_info.get("total_pages", 1)
            if total_pages > 1:
                estimated_pages = self._estimate_chunk_page_by_position(
                    chunk_index, total_chunks, total_pages
                )
                if estimated_pages and estimated_pages != [1]:
                    chunk_pages = estimated_pages
                    self.logger.info(f"Used position-based estimation for chunk {chunk_index}: pages {chunk_pages}")
        
        if not chunk_pages:
            chunk_pages = [1]
        
        enhanced_metadata.update({
            "page_numbers": chunk_pages,
            "page_range": self._format_page_range(chunk_pages),
            "primary_page": chunk_pages[0] if chunk_pages else 1
        })
        
        header_hierarchy = self._extract_header_hierarchy(header_metadata, chunk_content)
        enhanced_metadata.update({
            "header_hierarchy": header_hierarchy,
            "section_path": self._create_section_path(header_hierarchy),
            "primary_header": header_hierarchy.get("Header 1") or header_hierarchy.get("Header 2") or f"Section {chunk_index + 1}"
        })
        
        content_analysis = self._analyze_chunk_content(chunk_content)
        enhanced_metadata.update({
            "content_type": content_analysis["content_type"],
            "contains_financial_metrics": content_analysis["contains_financial_metrics"],
            "contains_tables": content_analysis["contains_tables"],
            "contains_figures": content_analysis["contains_figures"],
            "key_topics": content_analysis["key_topics"],
            "named_entities": content_analysis["named_entities"],
            "semantic_density": content_analysis["semantic_density"]
        })
        
        if base_metadata and "tables_summary" in base_metadata:
            chunk_specific_tables = self._filter_tables_for_chunk(
                chunk_content, 
                base_metadata["tables_summary"], 
                chunk_pages
            )
            if chunk_specific_tables["total_tables"] > 0:
                enhanced_metadata["tables_summary"] = chunk_specific_tables
                self.logger.info(f"Added {chunk_specific_tables['total_tables']} chunk-specific tables to metadata")
            else:
                if "tables_summary" in enhanced_metadata:
                    del enhanced_metadata["tables_summary"]
                self.logger.debug(f"No tables found for chunk {chunk_index}, removed tables_summary from metadata")
        else:
            if "tables_summary" in enhanced_metadata:
                del enhanced_metadata["tables_summary"]
            self.logger.debug(f"No tables_summary found in base_metadata. Available keys: {list(base_metadata.keys()) if base_metadata else 'No base_metadata'}")
        
        # Azure AI Search optimisation fields
        enhanced_metadata.update({
            "primary_header": header_hierarchy.get("Header 1", ""),
            "secondary_header": header_hierarchy.get("Header 2", ""),
            "tertiary_header": header_hierarchy.get("Header 3", ""),
            "all_headers": " ".join([h for h in header_hierarchy.values() if h]),
            "keywords": content_analysis["keywords"],
            "boost_score": self._calculate_boost_score(content_analysis, chunk_index, total_chunks),
            "filter_categories": self._create_filter_categories(base_metadata, content_analysis, document_context),
            "facet_fields": self._create_facet_fields(base_metadata, content_analysis, header_hierarchy)
        })
        
        # Document context
        enhanced_metadata["document_context"] = {
            "total_chunks": total_chunks,
            "document_length": document_context.get("document_length", 0),
            "document_complexity": document_context.get("document_complexity", "medium"),
            "source_type": document_context.get("source_type", "unknown"),
            "original_filename": document_context.get("original_filename", "unknown")
        }
        
        # Quality and relevance scoring
        enhanced_metadata.update({
            "chunk_quality_score": self._calculate_chunk_quality_score(chunk_content, content_analysis),
            "information_density": self._calculate_information_density(chunk_content),
            "readability_score": self._calculate_readability_score(chunk_content)
        })
        
        return enhanced_metadata

    def _format_page_range(self, page_numbers: List[int]) -> str:
        """
        Format page numbers into a readable range string.
        
        Args:
            page_numbers: List of page numbers
            
        Returns:
            Formatted page range string
        """
        if not page_numbers:
            return "1"
        
        if len(page_numbers) == 1:
            return str(page_numbers[0])
        
        consecutive_ranges = []
        start = page_numbers[0]
        end = start
        
        for i in range(1, len(page_numbers)):
            if page_numbers[i] == end + 1:
                end = page_numbers[i]
            else:
                if start == end:
                    consecutive_ranges.append(str(start))
                else:
                    consecutive_ranges.append(f"{start}-{end}")
                start = page_numbers[i]
                end = start
        
        if start == end:
            consecutive_ranges.append(str(start))
        else:
            consecutive_ranges.append(f"{start}-{end}")
        
        return ", ".join(consecutive_ranges)

    def _extract_header_hierarchy(self, header_metadata: Dict[str, Any], chunk_content: str) -> Dict[str, str]:
        """Extract header hierarchy from metadata and content."""
        hierarchy = {}
        
        for key, value in header_metadata.items():
            if key.startswith("Header") and value:
                hierarchy[key] = str(value).strip()
        
        if not hierarchy:
            header_patterns = [
                (r'^# (.+)$', "Header 1"),
                (r'^## (.+)$', "Header 2"),
                (r'^### (.+)$', "Header 3"),
                (r'^#### (.+)$', "Header 4"),
                (r'^##### (.+)$', "Header 5"),
                (r'^###### (.+)$', "Header 6")
            ]
            
            for pattern, header_level in header_patterns:
                matches = re.findall(pattern, chunk_content, re.MULTILINE)
                if matches:
                    hierarchy[header_level] = matches[0].strip()
                    break
        
        return hierarchy

    def _create_section_path(self, header_hierarchy: Dict[str, str]) -> str:
        """Create a hierarchical section path."""
        path_parts = []
        for level in ["Header 1", "Header 2", "Header 3", "Header 4", "Header 5", "Header 6"]:
            if level in header_hierarchy:
                path_parts.append(header_hierarchy[level])
        
        return " > ".join(path_parts) if path_parts else "Root"

    def _analyze_chunk_content(self, content: str) -> Dict[str, Any]:
        """
        Analyze chunk content for metadata enhancement.
        
        This method performs detailed content analysis to extract meaningful information
        about the chunk, including financial metrics detection, content type classification,
        table and figure detection, topic extraction, and keyword identification.
        
        The analysis results are used to enhance search capabilities, enable content
        filtering, and provide rich context for the RAG system.
        
        Args:
            content: Text content of the chunk to analyze.
        
        Returns:
            Dict[str, Any]: Comprehensive content analysis containing:
                - content_type: Classified type (e.g., "tabular_data", "financial_data", "executive_summary")
                - contains_financial_metrics: Boolean indicating presence of financial data
                - contains_tables: Boolean indicating presence of table structures
                - contains_figures: Boolean indicating presence of figures or charts
                - key_topics: List of identified financial topics (e.g., ["revenue", "profitability"])
                - named_entities: List of extracted entities (companies, years, currencies)
                - keywords: List of important keywords for search optimization
                - semantic_density: Float indicating information richness (0.0-1.0)

        Note:
            The analysis includes specialized detection for:
            - Financial patterns: currency amounts, percentages, financial ratios, quarters and fiscal years
            - Table structures: markdown tables, HTML tables, table references
            - Content classification: executive summaries, conclusions, risk sections
            - Topic extraction: revenue, profitability, growth, sustainability, etc.
            - Entity recognition: company names, years, currencies
            
            The semantic density score helps identify information-rich content
            for prioritization in search results.
        
        Returns:
            All analysis results are designed to enhance Azure AI Search capabilities
            and provide meaningful context for financial document retrieval.
        """
        financial_patterns = [
            r'\$[\d,]+(?:\.\d{2})?[MBK]?',  # Dollar amounts
            r'\d+(?:\.\d+)?%',  # Percentages
            r'(?:revenue|profit|loss|EBITDA|margin|ROI|ROE|EPS)\s*:?\s*\$?[\d,]+',  # Financial terms
            r'(?:Q[1-4]|FY)\s*\d{4}',  # Quarters and fiscal years
        ]
        
        contains_financial_metrics = any(re.search(pattern, content, re.IGNORECASE) for pattern in financial_patterns)
        
        contains_tables = self._detect_tables_in_content(content)
        
        contains_figures = bool(re.search(r'!\[.*?\]\(.*?\)', content) or
                               re.search(r'Figure\s+\d+', content, re.IGNORECASE) or
                               re.search(r'Chart\s+\d+', content, re.IGNORECASE))
        
        content_type = self._classify_content_type(content)
        
        key_topics = self._extract_key_topics(content)
        
        named_entities = self._extract_named_entities(content)
        
        keywords = self._extract_keywords(content)
        
        semantic_density = self._calculate_semantic_density(content)
        
        return {
            "content_type": content_type,
            "contains_financial_metrics": contains_financial_metrics,
            "contains_tables": contains_tables,
            "contains_figures": contains_figures,
            "key_topics": key_topics,
            "named_entities": named_entities,
            "keywords": keywords,
            "semantic_density": semantic_density
        }

    def _detect_tables_in_content(self, content: str) -> bool:
        """
        Table detection in document content using multiple strategies.
        
        This method employs sophisticated detection algorithms to identify tables
        in various formats including markdown tables, HTML tables, and table
        references. It validates detected tables to ensure they contain meaningful
        tabular data rather than formatting artifacts.
        
        Args:
            content: Text content to analyze for table presence.
        
        Returns:
            bool: True if valid tables are detected, False otherwise.
        
        Example:
            ```python
            # Markdown table content
            content = "|Year|Revenue|\\n|2023|$100M|\\n|2024|$115M|"
            has_tables = chunker._detect_tables_in_content(content)  # True
            
            # HTML table content
            content = "<table><tr><td>Year</td><td>Revenue</td></tr><tr><td>2023</td><td>$100M</td></tr></table>"
            has_tables = chunker._detect_tables_in_content(content)  # True
            
            # Table reference
            content = "See Table 1 below for detailed financial results"
            has_tables = chunker._detect_tables_in_content(content)  # True
            ```
        
        Note:
            The method validates tables by:
            - Counting table rows to ensure minimum data content (≥2 rows)
            - Checking for proper table structure and formatting
            - Identifying table references in surrounding text
            - Filtering out single-row formatting artifacts
            
            Detection strategies in order of preference:
            1. Markdown tables with pipe separators
            2. HTML table elements with proper structure
            3. Textual references to tables ("Table 1", "following table", etc.)
        """
        has_markdown_table = bool(re.search(r'\|.*\|.*\|', content) or 
                                 re.search(r'^\s*\|.*\|\s*$', content, re.MULTILINE))
        
        if has_markdown_table:
            table_lines = len(re.findall(r'^\s*\|.*\|\s*$', content, re.MULTILINE))
            if table_lines >= 2:
                return True
        
        has_html_table = bool(re.search(r'<table[^>]*>', content, re.IGNORECASE))
        if has_html_table:
            table_rows = len(re.findall(r'<tr[^>]*>', content, re.IGNORECASE))
            if table_rows >= 2:
                return True

        table_references = bool(re.search(r'table\s+\d+', content, re.IGNORECASE) or
                               re.search(r'the\s+following\s+table', content, re.IGNORECASE) or
                               re.search(r'table\s+below', content, re.IGNORECASE))
        
        return table_references

    def _is_table_in_chunk(self, chunk_content: str, table_data: Dict[str, Any]) -> bool:
        """Check if a table from document processing appears in the current chunk."""
        if "data" not in table_data or not table_data["data"]:
            return False
        
        table_rows = table_data["data"]
        if not table_rows:
            return False
        
        # Strategy 1: Check if the chunk contains a markdown table that matches this table's structure
        if self._chunk_contains_matching_markdown_table(chunk_content, table_data):
            return True
        
        # Strategy 2: Check for multiple distinctive elements from the table
        matching_elements = 0
        total_elements_checked = 0
        
        first_row = table_rows[0] if table_rows else []
        if first_row:
            for cell in first_row:
                if cell and str(cell).strip() and len(str(cell).strip()) > 2:
                    cell_text = str(cell).strip()
                    if self._is_distinctive_table_element(cell_text):
                        total_elements_checked += 1
                        if cell_text.lower() in chunk_content.lower():
                            matching_elements += 1
        
        for row in table_rows[1:3]:
            if row:
                for cell in row:
                    if cell and str(cell).strip() and len(str(cell).strip()) > 3:
                        cell_text = str(cell).strip()
                        if self._is_distinctive_table_element(cell_text):
                            total_elements_checked += 1
                            if cell_text.lower() in chunk_content.lower():
                                matching_elements += 1
        
        # Require at least 2 distinctive matching elements and >50% match rate
        if total_elements_checked >= 2 and matching_elements >= 2:
            match_rate = matching_elements / total_elements_checked
            return match_rate > 0.5
        
        return False

    def _chunk_contains_matching_markdown_table(self, chunk_content: str, table_data: Dict[str, Any]) -> bool:
        """Check if chunk contains a markdown table that matches the table data structure."""
        table_pattern = r'\|.*\|.*\n(?:\|.*\|.*\n)+'
        markdown_tables = re.findall(table_pattern, chunk_content)
        
        if not markdown_tables:
            return False
        
        table_rows = table_data.get("data", [])
        if not table_rows:
            return False
        
        expected_row_count = table_data.get("row_count", len(table_rows))
        expected_col_count = table_data.get("column_count", len(table_rows[0]) if table_rows else 0)
        
        for markdown_table in markdown_tables:
            lines = [line.strip() for line in markdown_table.strip().split('\n') if line.strip()]
            
            # Skip separator lines (lines with only |, -, and spaces)
            data_lines = [line for line in lines if not re.match(r'^\s*\|[\s\-\|]*\|\s*$', line)]
            
            if len(data_lines) >= 2:  # At least header + 1 data row
                # Check column count
                first_line_cols = len([cell.strip() for cell in data_lines[0].split('|')[1:-1] if cell.strip()])
                
                # Allow some tolerance in dimensions
                if (abs(len(data_lines) - expected_row_count) <= 1 and 
                    abs(first_line_cols - expected_col_count) <= 1):
                    
                    # Check if headers match
                    markdown_headers = [cell.strip() for cell in data_lines[0].split('|')[1:-1]]
                    table_headers = [str(cell).strip() for cell in table_rows[0]] if table_rows else []
                    
                    # Count matching headers
                    matching_headers = 0
                    for md_header in markdown_headers:
                        for table_header in table_headers:
                            if md_header.lower() == table_header.lower():
                                matching_headers += 1
                                break
                    
                    # If most headers match, consider it the same table
                    if matching_headers >= len(table_headers) * 0.7:  # 70% header match
                        return True
        
        return False

    def _is_distinctive_table_element(self, text: str) -> bool:
        """Check if a table element is distinctive enough to be used for matching."""
        text_lower = text.lower().strip()
        
        if len(text_lower) < 2:
            return False
        
        if not text_lower or text_lower.isspace():
            return False
        
        common_words = {
            'year', 'years', 'total', 'change', 'amount', 'value', 'item', 'name', 
            'description', 'type', 'category', 'date', 'time', 'number', 'count',
            'percent', 'percentage', 'rate', 'ratio', 'data', 'info', 'information'
        }
        
        if text_lower in common_words:
            return False
        
        if re.match(r'^\d+$', text_lower) and len(text_lower) < 4:  # Only skip short pure numbers
            return False
        
        if re.match(r'^20\d{2}$', text_lower):  # Years like 2023, 2024
            return True
        
        if re.match(r'^\d+\s*%', text_lower):  # Percentages like "4 %", "15%"
            return True
        
        if '%' in text_lower and len(text_lower) >= 3:
            return True
        
        generic_financial = {'q1', 'q2', 'q3', 'q4', 'fy', 'ytd', 'usd', 'eur', 'gbp'}
        if text_lower in generic_financial:
            return False

        if len(text_lower) >= 3:
            if any(c.isalpha() for c in text_lower):
                return True
            if re.search(r'\d{4}', text_lower):  # Contains a 4-digit year
                return True
            if re.search(r'\d+\s+\d+', text_lower):  # Contains space-separated numbers
                return True
        
        if len(text_lower) >= 2:
            has_letter = any(c.isalpha() for c in text_lower)
            has_digit = any(c.isdigit() for c in text_lower)
            if has_letter and has_digit:
                return True
            if has_letter and len(text_lower) >= 3:
                return True
        
        return False

    def _classify_content_type(self, content: str) -> str:
        """
        Classify the type of content in a chunk for enhanced metadata.
        
        This method analyses chunk content to determine its primary type, enabling
        better search filtering, content organisation, and user experience. The
        classification is specifically optimised for financial documents and
        corporate reports with priority given to tabular data detection.
        
        Args:
            content: Text content of the chunk to classify.
        
        Returns:
            str: Content type classification. Possible values:
                - "tabular_data": Content primarily containing tables (>30% table rows or >5 table lines)
                - "executive_summary": Executive summary or overview sections
                - "conclusion": Conclusion, summary, or outlook sections
                - "risk_governance": Risk management or governance content
                - "sustainability": Sustainability or ESG content
                - "financial_data": Financial metrics and analysis
                - "header_section": Short header or title sections (<50 words)
                - "content_section": General content sections (default)
        
        Example:
            ```python
            # Table-heavy content
            content = "|Year|Revenue|\\n|2023|$100M|\\n|2024|$115M|\\n|2025|$130M|"
            content_type = chunker._classify_content_type(content)  # "tabular_data"
            
            # Executive summary
            content = "## Executive Summary\\nThis report presents our financial performance..."
            content_type = chunker._classify_content_type(content)  # "executive_summary"
            
            # Financial analysis
            content = "Revenue increased by 15% to $100M with EBITDA margin improving to 20%"
            content_type = chunker._classify_content_type(content)  # "financial_data"
            
            # Short header
            content = "### Q4 2024 Results"
            content_type = chunker._classify_content_type(content)  # "header_section"
            ```
        
        Note:
            Classification priority (in order):
            1. Tabular data: Detected by table row ratio (>30%) or significant table content
            2. Specific section types: Based on keyword patterns in content
            3. Financial data: Presence of financial keywords and metrics
            4. Header sections: Short content (<50 words)
            5. General content: Default classification
            
            The classification is used for:
            - Search result filtering and organisation
            - Content prioritization and ranking
            - User interface customization
            - Analytics and reporting
            
            Table detection considers both markdown (pipe-separated) and HTML tables,
            with validation to ensure meaningful tabular content rather than formatting artifacts.
        """
        content_lower = content.lower()
        
        # Check for tables first (highest priority for tabular content)
        has_markdown_table = bool(re.search(r'\|.*\|.*\|', content) or 
                                 re.search(r'^\s*\|.*\|\s*$', content, re.MULTILINE))
        
        has_html_table = bool(re.search(r'<table[^>]*>', content, re.IGNORECASE))
        
        # Count table content to determine if it's primarily tabular
        if has_markdown_table:
            table_lines = len(re.findall(r'^\s*\|.*\|\s*$', content, re.MULTILINE))
            total_lines = len(content.split('\n'))
            table_ratio = table_lines / total_lines if total_lines > 0 else 0
            
            # If more than 30% of lines are table rows, classify as tabular_data
            if table_ratio > 0.3 or table_lines > 5:
                return "tabular_data"
        
        elif has_html_table:
            table_rows = len(re.findall(r'<tr[^>]*>', content, re.IGNORECASE))
            table_cells = len(re.findall(r'<t[dh][^>]*>', content, re.IGNORECASE))
            
            if table_rows >= 3 or table_cells >= 6:
                return "tabular_data"
        
        # Check for other content types
        if re.search(r'(executive summary|overview|introduction)', content_lower):
            return "executive_summary"
        elif re.search(r'(conclusion|summary|outlook|future)', content_lower):
            return "conclusion"
        elif re.search(r'(risk|compliance|governance)', content_lower):
            return "risk_governance"
        elif re.search(r'(sustainability|environment|social)', content_lower):
            return "sustainability"
        elif re.search(r'(financial|revenue|profit|income|balance sheet)', content_lower):
            return "financial_data"
        elif len(content.split()) < 50:
            return "header_section"
        else:
            return "content_section"

    def _extract_key_topics(self, content: str) -> List[str]:
        """
        Extract key financial topics from chunk content.
        
        This method identifies the main financial and business topics present in the
        content using keyword-based analysis.
        
        Args:
            content: Text content to analyze for topic extraction.
        
        Returns:
            List[str]: List of identified topics, limited to top 5. Possible topics include:
                "revenue", "profitability", "growth", "performance", "risk", 
                "sustainability", "strategy", "market"
        
        Example:
            ```python
            content = "Revenue increased 15% while EBITDA margin improved. Growth strategy focuses on sustainability."
            topics = chunker._extract_key_topics(content)
            # Returns: ["revenue", "profitability", "growth", "sustainability", "strategy"]
            ```
        
        Note:
            Topics are identified based on keyword matching with predefined financial
            topic categories. The method is optimised for financial and corporate content.
        """
        financial_topics = {
            "revenue": ["revenue", "sales", "income", "turnover"],
            "profitability": ["profit", "margin", "ebitda", "earnings"],
            "growth": ["growth", "increase", "expansion", "development"],
            "performance": ["performance", "results", "achievement", "success"],
            "risk": ["risk", "uncertainty", "challenge", "threat"],
            "sustainability": ["sustainability", "environment", "social", "esg"],
            "strategy": ["strategy", "plan", "vision", "objective"],
            "market": ["market", "industry", "sector", "competition"]
        }
        
        content_lower = content.lower()
        topics = []
        
        for topic, keywords in financial_topics.items():
            if any(keyword in content_lower for keyword in keywords):
                topics.append(topic)
        
        return topics[:5]

    def _extract_named_entities(self, content: str) -> List[str]:
        """Extract named entities (simplified implementation)."""
        entities = []
        
        company_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Inc|Corp|Ltd|LLC|AG|GmbH|SA|plc)\b'
        companies = re.findall(company_pattern, content)
        entities.extend(companies[:3])
        
        years = re.findall(r'\b(20\d{2})\b', content)
        entities.extend(list(set(years))[:3])
        
        currencies = re.findall(r'\b(USD|EUR|GBP|JPY|CHF)\b', content)
        entities.extend(list(set(currencies)))
        
        return entities

    def _extract_keywords(self, content: str) -> List[str]:
        """
        Extract important keywords for search optimization.
        
        This method identifies the most significant keywords in the content by analysing
        word frequency while filtering out common stop words. The extracted keywords
        are used to enhance search capabilities and content discoverability.
        
        Args:
            content: Text content to analyse for keyword extraction.
        
        Returns:
            List[str]: List of top 10 keywords ranked by frequency, excluding stop words.
        
        Example:
            ```python
            content = "Financial performance improved significantly with revenue growth and margin expansion."
            keywords = chunker._extract_keywords(content)
            # Returns: ["financial", "performance", "revenue", "growth", "margin", ...]
            ```
        
        Note:
            The method filters out common stop words and focuses on meaningful terms
            (≥3 characters) that are likely to be useful for search and categorization.
        """
        stop_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can", "shall"}
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', content.lower())
        
        word_freq = {}
        for word in words:
            if word not in stop_words and len(word) > 2:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:10]]

    def _calculate_semantic_density(self, content: str) -> float:
        """
        Calculate semantic density using linguistic research principles.
        
        Based on:
        - Zipf's Law for word frequency distribution
        - Information theory (Shannon entropy)
        - Computational linguistics research on content words vs function words
        
        This method identifies content words (nouns, verbs, adjectives, adverbs) vs
        function words (articles, prepositions, conjunctions) using linguistic patterns.
        
        Args:
            content: Text content to analyze for semantic density.
        
        Returns:
            float: Semantic density score between 0.0 and 1.0
        """
        words = content.split()
        if not words:
            return 0.0
        
        content_word_count = 0
        
        # Function words (based on linguistic research)
        function_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 
            'may', 'might', 'must', 'can', 'shall', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
        
        for word in words:
            clean_word = word.lower().strip('.,!?;:"()[]{}')
            
            # Content word criteria (linguistic research-based):
            # 1. Not a function word
            # 2. Length >= 3 (morphological minimum for content words)
            # 3. Contains alphabetic characters (not just numbers/symbols)
            # 4. Not a common discourse marker
            
            if (clean_word not in function_words and 
                len(clean_word) >= 3 and 
                any(c.isalpha() for c in clean_word) and
                not clean_word in {'very', 'really', 'quite', 'just', 'only', 'also', 'even'}):
                content_word_count += 1
        
        # Calculate density as ratio of content words to total words
        density = content_word_count / len(words) if words else 0.0
        
        # Apply linguistic normalization (typical content word ratio is 0.4-0.7)
        # Normalize to 0-1 scale where 0.6 = 1.0 (optimal density)
        normalized_density = min(density / 0.6, 1.0)
        
        return round(normalized_density, 3)

    def _calculate_boost_score(self, content_analysis: Dict[str, Any], chunk_index: int, total_chunks: int) -> float:
        """Calculate boost score for search ranking."""
        score = 1.0
        
        # Boost for financial content
        if content_analysis["contains_financial_metrics"]:
            score += 0.3
        
        # Boost for tables (structured data)
        if content_analysis["contains_tables"]:
            score += 0.2
        
        # Boost for executive summary or conclusion
        if content_analysis["content_type"] in ["executive_summary", "conclusion"]:
            score += 0.4
        
        # Slight boost for early chunks (often contain important info)
        if chunk_index < total_chunks * 0.2:
            score += 0.1
        
        # Boost for high semantic density
        if content_analysis["semantic_density"] > 0.7:
            score += 0.1
        
        return round(score, 2)

    def _create_filter_categories(self, base_metadata: Dict[str, Any], content_analysis: Dict[str, Any], document_context: Dict[str, Any]) -> Dict[str, str]:
        """Create filter categories for Azure AI Search."""
        categories = {
            "content_type": content_analysis["content_type"],
            "has_financial_metrics": str(content_analysis["contains_financial_metrics"]).lower(),
            "has_tables": str(content_analysis["contains_tables"]).lower(),
            "has_figures": str(content_analysis["contains_figures"]).lower(),
            "document_type": document_context.get("source_type", "unknown"),
            "complexity": document_context.get("document_complexity", "medium")
        }
        
        if base_metadata:
            doc_id = base_metadata.get("document_identification", {})
            categories.update({
                "file_type": doc_id.get("content_type", "unknown"),
                "language": doc_id.get("language", "unknown")
            })
        
        return categories

    def _create_facet_fields(self, base_metadata: Dict[str, Any], content_analysis: Dict[str, Any], header_hierarchy: Dict[str, str]) -> Dict[str, str]:
        """Create facet fields for Azure AI Search."""
        facets = {
            "content_type": content_analysis["content_type"],
            "primary_section": header_hierarchy.get("Header 1", "Unknown"),
            "secondary_section": header_hierarchy.get("Header 2", "Unknown"),
            "has_financial_data": str(content_analysis["contains_financial_metrics"]).lower(),
            "has_structured_data": str(content_analysis["contains_tables"]).lower()
        }
        
        # Add key topics as facets
        if content_analysis["key_topics"]:
            facets["primary_topic"] = content_analysis["key_topics"][0]
        
        return facets

    def _calculate_chunk_quality_score(self, content: str, content_analysis: Dict[str, Any]) -> float:
        """
        Calculate chunk quality score based on information retrieval research.
        
        This scoring method is based on established IR principles:
        - Content length optimization (Karpukhin et al., 2020 - DPR paper)
        - Information density (Shannon entropy principles)
        - Structural indicators (financial document analysis)
        - Semantic richness (topic diversity)
        
        Score components:
        - Base readability: 0.3 (30%)
        - Length optimization: 0.25 (25%) 
        - Information density: 0.25 (25%)
        - Domain relevance: 0.2 (20%)
        
        Returns:
            float: Quality score between 0.0 and 1.0
        """
        # Component 1: Base readability (30% weight)
        readability_score = self._calculate_readability_score(content)
        readability_component = 0.3 * readability_score
        
        # Component 2: Length optimization (25% weight)
        # Based on DPR research: 100-200 tokens optimal for retrieval
        word_count = len(content.split())
        if 75 <= word_count <= 300:  # Optimal range for RAG retrieval
            length_score = 1.0
        elif 50 <= word_count < 75 or 300 < word_count <= 500:
            length_score = 0.8  # Good but not optimal
        elif 25 <= word_count < 50 or 500 < word_count <= 750:
            length_score = 0.6  # Acceptable
        elif word_count < 25:
            length_score = 0.3  # Too short, likely incomplete
        else:  # > 750 words
            length_score = 0.4  # Too long, may hurt retrieval precision
        
        length_component = 0.25 * length_score
        
        # Component 3: Information density (25% weight)
        semantic_density = content_analysis["semantic_density"]
        # Normalize semantic density to 0-1 scale with sigmoid-like curve
        if semantic_density >= 0.7:
            density_score = 1.0
        elif semantic_density >= 0.5:
            density_score = 0.8
        elif semantic_density >= 0.3:
            density_score = 0.6
        else:
            density_score = 0.4
        
        density_component = 0.25 * density_score
        
        # Component 4: Domain relevance for financial documents (20% weight)
        domain_score = 0.5  

        # Financial content indicators (research-based weights)
        if content_analysis["contains_financial_metrics"]:
            domain_score += 0.2  # Financial metrics are highly valuable
        if content_analysis["contains_tables"]:
            domain_score += 0.15  # Structured data is valuable for analysis
        
        # Topic diversity (information theory principle)
        topic_count = len(content_analysis["key_topics"])
        if topic_count >= 3:
            domain_score += 0.1  # High topic diversity
        elif topic_count >= 2:
            domain_score += 0.05  # Moderate topic diversity
        
        # Content type bonus
        content_type = content_analysis["content_type"]
        if content_type in ["executive_summary", "financial_data", "tabular_data"]:
            domain_score += 0.1  # High-value content types
        elif content_type in ["conclusion", "risk_governance"]:
            domain_score += 0.05  # Moderate-value content types
        
        domain_score = min(domain_score, 1.0)  # Cap at 1.0
        domain_component = 0.2 * domain_score
        
        final_score = readability_component + length_component + density_component + domain_component
        
        return round(min(final_score, 1.0), 3)

    def _calculate_information_density(self, content: str) -> float:
        """
        Calculate information density using TF-IDF principles and information theory.
        
        Based on established information retrieval research:
        - Term Frequency analysis for content significance
        - Information theory (Shannon entropy)
        - Domain-specific term weighting for financial documents
        - Named entity recognition patterns
        
        This provides a more sophisticated measure than simple word counting.
        
        Returns:
            float: Information density score between 0.0 and 1.0
        """
        words = content.split()
        if not words:
            return 0.0
        
        # Component 1: Financial domain terms (higher weight)
        financial_terms = {
            'revenue', 'profit', 'ebitda', 'margin', 'growth', 'performance', 
            'investment', 'return', 'yield', 'equity', 'debt', 'asset', 'liability',
            'cash', 'flow', 'earnings', 'dividend', 'shareholder', 'quarter',
            'fiscal', 'budget', 'forecast', 'valuation', 'risk', 'compliance'
        }
        
        financial_term_count = sum(1 for word in words 
                                 if word.lower().strip('.,!?;:"()[]{}') in financial_terms)
        
        # Component 2: Numerical data (financial figures, percentages, dates)
        numerical_patterns = [
            r'\$[\d,]+(?:\.\d{2})?[MBK]?',  # Currency amounts
            r'\d+(?:\.\d+)?%',  # Percentages
            r'\b\d{4}\b',  # Years
            r'\b\d+(?:,\d{3})*(?:\.\d+)?\b',  # Large numbers
            r'Q[1-4]',  # Quarters
        ]
        
        numerical_count = sum(len(re.findall(pattern, content, re.IGNORECASE)) 
                            for pattern in numerical_patterns)
        
        # Component 3: Named entities (simplified pattern matching)
        # Company indicators, proper nouns
        entity_patterns = [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Inc|Corp|Ltd|LLC|AG|GmbH|SA|plc)\b',
            r'\b[A-Z]{2,}\b',  # Acronyms
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b'  # Proper noun phrases
        ]
        
        entity_count = sum(len(re.findall(pattern, content)) 
                         for pattern in entity_patterns)
        
        # Component 4: Technical/specialized vocabulary
        # Words longer than 7 characters (often technical terms)
        technical_words = [word for word in words 
                         if len(word.strip('.,!?;:"()[]{}')) > 7 
                         and word.isalpha()]
        
        # Calculate weighted information score
        info_score = 0
        
        # Financial terms: 40% weight (domain-specific high value)
        financial_density = financial_term_count / len(words)
        info_score += 0.4 * min(financial_density * 10, 1.0)

        # Numerical data: 30% weight (structured information)
        numerical_density = numerical_count / len(words)
        info_score += 0.3 * min(numerical_density * 5, 1.0)
        
        # Named entities: 20% weight (specific information)
        entity_density = entity_count / len(words)
        info_score += 0.2 * min(entity_density * 8, 1.0)
        
        # Technical vocabulary: 10% weight (complexity indicator)
        technical_density = len(technical_words) / len(words)
        info_score += 0.1 * min(technical_density * 3, 1.0)
        
        return round(min(info_score, 1.0), 3)

    def _calculate_readability_score(self, content: str) -> float:
        """
        Calculate readability score using the Flesch Reading Ease formula.
        
        Based on Rudolf Flesch's research (1948) and validated by decades of studies.
        Formula: 206.835 - (1.015 × ASL) - (84.6 × ASW)
        Where:
        - ASL = Average Sentence Length (words per sentence)
        - ASW = Average Syllables per Word
        
        Score interpretation:
        - 90-100: Very Easy (5th grade level)
        - 80-89: Easy (6th grade level)
        - 70-79: Fairly Easy (7th grade level)
        - 60-69: Standard (8th-9th grade level)
        - 50-59: Fairly Difficult (10th-12th grade level)
        - 30-49: Difficult (college level)
        - 0-29: Very Difficult (graduate level)
        
        Returns:
            float: Normalized readability score between 0.0 and 1.0
        """
        sentences = [s.strip() for s in re.split(r'[.!?]+', content) if s.strip()]
        words = content.split()
        
        if not sentences or not words:
            return 0.0
        
        # Calculate Average Sentence Length
        asl = len(words) / len(sentences)
        
        # Calculate Average Syllables per Word (simplified syllable counting)
        total_syllables = 0
        for word in words:
            # Remove punctuation and convert to lowercase
            clean_word = re.sub(r'[^a-zA-Z]', '', word.lower())
            if clean_word:
                # Simplified syllable counting (research-based heuristics)
                syllables = max(1, len(re.findall(r'[aeiouy]+', clean_word)))
                # Adjust for common patterns
                if clean_word.endswith('e'):
                    syllables -= 1
                if clean_word.endswith('le') and len(clean_word) > 2:
                    syllables += 1
                total_syllables += max(1, syllables)
        
        asw = total_syllables / len(words) if words else 1.0
        
        # Flesch Reading Ease formula
        flesch_score = 206.835 - (1.015 * asl) - (84.6 * asw)
        
        # Normalize to 0-1 scale (0 = very difficult, 1 = very easy)
        # Flesch scores typically range from 0-100
        normalized_score = max(0.0, min(1.0, flesch_score / 100.0))
        
        return round(normalized_score, 3)

    def _assess_document_complexity(self, text: str) -> str:
        """
        Assess document complexity using computational linguistics research.
        
        Based on multiple complexity indicators from academic research:
        - Syntactic complexity (sentence length distribution)
        - Lexical diversity (Type-Token Ratio)
        - Domain-specific complexity (financial terminology density)
        - Structural complexity (formatting and organisation)
        
        References:
        - Lu, X. (2010). Automatic analysis of syntactic complexity
        - Jarvis, S. (2013). Capturing the diversity in lexical diversity
        - Financial document complexity research
        
        Returns:
            str: Complexity level ("low", "medium", "high")
        """
        words = text.split()
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        
        if not words or not sentences:
            return "low"
        
        # Component 1: Syntactic Complexity (sentence length variation)
        sentence_lengths = [len(s.split()) for s in sentences]
        avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths)
        
        # Calculate coefficient of variation for sentence length
        if len(sentence_lengths) > 1:
            import statistics
            sentence_length_cv = statistics.stdev(sentence_lengths) / avg_sentence_length
        else:
            sentence_length_cv = 0
        
        # Component 2: Lexical Diversity (Type-Token Ratio)
        unique_words = set(word.lower().strip('.,!?;:"()[]{}') for word in words)
        ttr = len(unique_words) / len(words) if words else 0
        
        # Component 3: Domain-specific complexity (financial terminology)
        financial_terms = {
            'revenue', 'profit', 'ebitda', 'margin', 'equity', 'liability', 'asset',
            'depreciation', 'amortization', 'valuation', 'dividend', 'shareholder',
            'stakeholder', 'governance', 'compliance', 'audit', 'fiscal', 'quarter',
            'portfolio', 'investment', 'return', 'yield', 'volatility', 'liquidity'
        }
        
        financial_term_count = sum(1 for word in words 
                                 if word.lower().strip('.,!?;:"()[]{}') in financial_terms)
        financial_density = financial_term_count / len(words) if words else 0
        
        # Component 4: Structural complexity
        structural_indicators = 0
        structural_indicators += len(re.findall(r'\$[\d,]+', text))  # Financial figures
        structural_indicators += len(re.findall(r'\d+\.\d+%', text))  # Percentages
        structural_indicators += len(re.findall(r'\|.*\|', text))  # Tables
        structural_indicators += len(re.findall(r'#+ ', text))  # Headers
        
        structural_density = structural_indicators / len(words) if words else 0
        
        # Calculate composite complexity score
        complexity_score = 0
        
        # Syntactic complexity (25% weight)
        if avg_sentence_length > 20:
            complexity_score += 0.25
        elif avg_sentence_length > 12:
            complexity_score += 0.15
        else:
            complexity_score += 0.05
        
        # Sentence variation (15% weight)
        if sentence_length_cv > 0.5:
            complexity_score += 0.15
        elif sentence_length_cv > 0.3:
            complexity_score += 0.10
        else:
            complexity_score += 0.05
        
        # Lexical diversity (30% weight) - Higher TTR = more complex
        if ttr > 0.7:
            complexity_score += 0.30
        elif ttr > 0.5:
            complexity_score += 0.20
        else:
            complexity_score += 0.10
        
        # Financial terminology (20% weight)
        if financial_density > 0.05:  # >5% financial terms
            complexity_score += 0.20
        elif financial_density > 0.02:  # >2% financial terms
            complexity_score += 0.15
        else:
            complexity_score += 0.05
        
        # Structural complexity (10% weight)
        if structural_density > 0.1:
            complexity_score += 0.10
        elif structural_density > 0.05:
            complexity_score += 0.07
        else:
            complexity_score += 0.03
        
        # Determine complexity level based on composite score
        if complexity_score >= 0.7:
            return "high"
        elif complexity_score >= 0.4:
            return "medium"
        else:
            return "low"

    def _extract_content_themes(self, text: str) -> List[str]:
        """Extract main content themes from the document."""
        themes = []
        text_lower = text.lower()
        
        theme_keywords = {
            "financial_performance": ["revenue", "profit", "earnings", "financial", "performance"],
            "growth_strategy": ["growth", "strategy", "expansion", "development", "future"],
            "risk_management": ["risk", "compliance", "governance", "management"],
            "sustainability": ["sustainability", "environment", "social", "esg"],
            "market_analysis": ["market", "industry", "competition", "analysis"],
            "operations": ["operations", "business", "operational", "efficiency"]
        }
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                themes.append(theme)
        
        return themes

    def _detect_financial_indicators(self, text: str) -> List[str]:
        """Detect financial indicators in the text."""
        indicators = []
        
        financial_patterns = {
            "revenue": r'revenue|sales|turnover',
            "profit": r'profit|earnings|ebitda',
            "margin": r'margin|profitability',
            "growth": r'growth|increase|decrease',
            "ratio": r'ratio|percentage|%',
            "currency": r'\$|€|£|¥|USD|EUR|GBP'
        }
        
        for indicator, pattern in financial_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                indicators.append(indicator)
        
        return indicators

    def _count_tables_in_text(self, text: str) -> int:
        """Count tables in the text."""
        markdown_tables = len(re.findall(r'\|.*\|.*\n(?:\|.*\|.*\n)*', text))
        
        table_refs = len(re.findall(r'table\s+\d+', text, re.IGNORECASE))
        
        return max(markdown_tables, table_refs)

    def _count_figures_in_text(self, text: str) -> int:
        """Count figures/images in the text."""
        markdown_images = len(re.findall(r'!\[.*?\]\(.*?\)', text))
        
        figure_refs = len(re.findall(r'figure\s+\d+|chart\s+\d+', text, re.IGNORECASE))
        
        return max(markdown_images, figure_refs)
    
    def _extract_text_and_metadata(self, documents):
        """
        Extract text content and metadata from various document formats.
        
        This method provides a unified interface for extracting text and metadata from
        different document input formats. It handles the complexity of various input
        types and ensures consistent output format for the chunking pipeline.
        
        The method supports multiple input formats commonly used in document processing
        pipelines, including raw text, LangChain documents, and processed results from
        Azure Document Intelligence.
        
        Args:
            documents: Document input in one of the supported formats:
                - str: Plain text content
                - Document: Single LangChain Document object
                - List[Document]: Multiple LangChain Documents to concatenate
                - dict: Processed document result from Azure Document Intelligence
        
        Returns:
            Tuple[str, Dict[str, Any]]: A tuple containing:
                - str: Extracted text content ready for chunking
                - Dict[str, Any]: Combined metadata from all sources
        
        Raises:
            TypeError: If the input format is not supported.
            ValueError: If the input is None or contains no valid content.
        
        Example:
            ```python
            # Extract from plain text
            text, metadata = chunker._extract_text_and_metadata("Sample text content")
            
            # Extract from LangChain Document
            doc = Document(page_content="Content", metadata={"source": "file.pdf"})
            text, metadata = chunker._extract_text_and_metadata(doc)
            
            # Extract from processed document result
            processed_doc = {
                "document_id": "doc_123",
                "content": {"markdown": "# Title\\nContent..."},
                "metadata": {"document_identification": {...}}
            }
            text, metadata = chunker._extract_text_and_metadata(processed_doc)
            
            print(f"Extracted {len(text)} characters")
            print(f"Metadata keys: {list(metadata.keys())}")
            ```
        
        Note:
            For processed document results, the method prefers markdown content over
            plain text when available, as markdown preserves document structure
            better for header-based chunking.
            
            When processing multiple documents, metadata is merged with later
            documents potentially overriding earlier values for conflicting keys.
            
            The method logs the extraction strategy used for debugging purposes.
        
        Warning:
            If no valid content is found in the input, the method returns empty
            text and logs a warning. This may indicate issues with document
            processing or unsupported input formats.
        """
        metadata = {}
        
        if isinstance(documents, str):
            return documents, metadata
        
        elif isinstance(documents, Document):
            return documents.page_content, documents.metadata
        
        elif isinstance(documents, list) and all(isinstance(doc, Document) for doc in documents):
            combined_text = "\n\n".join(doc.page_content for doc in documents)
            for doc in documents:
                metadata.update(doc.metadata)
            return combined_text, metadata
        
        elif isinstance(documents, dict):
            self.logger.info("Extracting text and metadata from processed document result")
            
            if "document_id" in documents:
                metadata["document_id"] = documents["document_id"]
            
            if "metadata" in documents:
                metadata.update(documents["metadata"])
            
            if "content" in documents and isinstance(documents["content"], dict):
                content_dict = documents["content"]
                if "tables_summary" in content_dict:
                    metadata["tables_summary"] = content_dict["tables_summary"]
            
            if "content" in documents and isinstance(documents["content"], dict):
                content_dict = documents["content"]
                
                if "markdown" in content_dict and content_dict["markdown"]:
                    self.logger.info("Using markdown content for chunking")
                    return content_dict["markdown"], metadata
                
                # Fall back to text content
                elif "text" in content_dict and content_dict["text"]:
                    self.logger.info("Using text content for chunking")
                    return content_dict["text"], metadata
                
                elif isinstance(content_dict, str):
                    self.logger.info("Using raw content string for chunking")
                    return content_dict, metadata
            
            elif "content" in documents and isinstance(documents["content"], str):
                self.logger.info("Using legacy content format for chunking")
                return documents["content"], metadata
            
            self.logger.warning("No valid content found in document")
            return "", metadata
        
        else:
            self.logger.warning(f"Unsupported document format: {type(documents)}")
            return "", metadata

    def _extract_page_info_from_metadata(self, base_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract page information from document metadata.
        
        Args:
            base_metadata: Base document metadata
            
        Returns:
            Dictionary containing page information
        """
        page_info = {
            "total_pages": 1,
            "has_page_breaks": False,
            "page_dimensions": None
        }
        
        if not base_metadata:
            return page_info
        
        doc_structure = base_metadata.get("document_structure", {})
        page_summary = doc_structure.get("page_summary", {})
        
        if page_summary:
            page_info["total_pages"] = page_summary.get("page_count", 1)
            page_info["page_dimensions"] = page_summary.get("page_dimensions")
            
            pages_processed = page_summary.get("pages_processed", "all")
            if pages_processed != "all":
                page_info["pages_processed"] = pages_processed
        
        self.logger.info(f"Extracted page info from metadata: {page_info['total_pages']} total pages")
        return page_info

    def _estimate_chunk_page_by_position(self, chunk_index: int, total_chunks: int, total_pages: int) -> List[int]:
        """
        Estimate chunk page based on its position in the document.
        
        Args:
            chunk_index: Index of the chunk (0-based)
            total_chunks: Total number of chunks
            total_pages: Total number of pages in document
            
        Returns:
            List of estimated page numbers
        """
        if total_pages <= 1:
            return [1]
        
        # Estimate which page this chunk might be on based on its position
        # This is a rough estimation assuming chunks are distributed evenly
        chunk_position_ratio = chunk_index / max(1, total_chunks - 1)
        estimated_page = max(1, min(total_pages, int(chunk_position_ratio * total_pages) + 1))
        
        # For chunks near boundaries, include adjacent pages
        if chunk_position_ratio < 0.1:  # First 10% of chunks
            return [1, min(2, total_pages)]
        elif chunk_position_ratio > 0.9:  # Last 10% of chunks
            return [max(1, total_pages - 1), total_pages]
        else:
            # Middle chunks might span adjacent pages
            prev_page = max(1, estimated_page - 1)
            next_page = min(total_pages, estimated_page + 1)
            return [prev_page, estimated_page, next_page] if estimated_page > 1 and estimated_page < total_pages else [estimated_page]

    def _filter_tables_for_chunk(
        self, 
        chunk_content: str, 
        tables_summary: Dict[str, Any], 
        chunk_pages: List[int]
    ) -> Dict[str, Any]:
        """
        Filter tables to only include those that are directly related to the current chunk.
        
        This method analyses the chunk content and page information to determine which
        tables from the document's tables_summary are actually present in or relevant
        to the current chunk. This ensures that each chunk only contains metadata
        for tables that are directly related to its content.
        
        Args:
            chunk_content: Text content of the current chunk
            tables_summary: Complete tables summary from document processing
            chunk_pages: List of page numbers that this chunk spans
            
        Returns:
            Dict[str, Any]: Filtered tables summary containing only chunk-relevant tables
        """
        if not tables_summary or "tables" not in tables_summary:
            return {"total_tables": 0, "tables": []}
        
        chunk_relevant_tables = []
        
        for table in tables_summary["tables"]:
            if self._is_table_relevant_to_chunk(chunk_content, table, chunk_pages):
                chunk_relevant_tables.append(table)
                self.logger.debug(f"Table {table.get('id', 'unknown')} is relevant to chunk")
            else:
                self.logger.debug(f"Table {table.get('id', 'unknown')} is NOT relevant to chunk")
        
        return {
            "total_tables": len(chunk_relevant_tables),
            "tables": chunk_relevant_tables
        }

    def _is_table_relevant_to_chunk(
        self, 
        chunk_content: str, 
        table_data: Dict[str, Any], 
        chunk_pages: List[int]
    ) -> bool:
        """
        Determine if a specific table is relevant to the current chunk.
        
        Uses multiple strategies to determine relevance:
        1. Content-based matching: Table data appears in chunk content (PRIMARY)
        2. Table reference matching: Table is explicitly referenced (SECONDARY)
        3. Page-based matching with strict content verification (TERTIARY)
        4. Proximity-based matching for adjacent pages (VERY RESTRICTIVE)
        
        Args:
            chunk_content: Text content of the current chunk
            table_data: Table data from document processing
            chunk_pages: List of page numbers that this chunk spans
            
        Returns:
            bool: True if table is relevant to this chunk
        """
        # Strategy 1: Content-based matching - PRIMARY STRATEGY
        if self._is_table_in_chunk(chunk_content, table_data):
            self.logger.debug("Table content found in chunk")
            return True
        
        # Strategy 2: Table reference matching - check for explicit table references
        table_id = table_data.get("id", "")
        if table_id:
            # Look for references like "Table 1", "table_1", etc.
            table_ref_patterns = [
                rf'\btable\s*{re.escape(table_id)}\b',
                rf'\btable\s*{re.escape(table_id.replace("table_", ""))}\b',
                rf'\b{re.escape(table_id)}\b'
            ]
            
            for pattern in table_ref_patterns:
                if re.search(pattern, chunk_content, re.IGNORECASE):
                    self.logger.debug(f"Found table reference pattern: {pattern}")
                    return True
        
        # Strategy 3: Page-based matching with VERY strict content verification
        table_page = table_data.get("page_number")
        if table_page and table_page in chunk_pages:
            table_keywords = self._extract_table_keywords(table_data)
            if table_keywords:
                chunk_lower = chunk_content.lower()
                keyword_matches = sum(1 for keyword in table_keywords if keyword.lower() in chunk_lower)
                
                # Much more restrictive: require at least 3 distinctive keyword matches
                # AND the keywords must be relatively unique (not just common terms like "2024")
                unique_keywords = self._filter_unique_keywords(table_keywords, chunk_content)
                unique_matches = sum(1 for keyword in unique_keywords if keyword.lower() in chunk_lower)
                
                # Only include if multiple unique keywords match (indicating substantial table discussion)
                if keyword_matches >= 3 and unique_matches >= 2:
                    self.logger.debug(f"Table on page {table_page} has {keyword_matches} keyword matches ({unique_matches} unique) in chunk")
                    return True
        
        # Strategy 4: Proximity-based matching for adjacent pages (VERY RESTRICTIVE)
        if table_page and chunk_pages:
            # Check if table is on adjacent pages (within 1 page of chunk)
            for chunk_page in chunk_pages:
                if abs(table_page - chunk_page) <= 1:
                    table_id_num = table_id.replace("table_", "") if table_id else ""
                    specific_table_refs = [
                        f"table {table_id_num}",
                        f"the table",
                        f"above table",
                        f"below table",
                        f"following table",
                        f"table above",
                        f"table below"
                    ]
                    
                    if any(ref in chunk_content.lower() for ref in specific_table_refs):
                        self.logger.debug(f"Table on adjacent page {table_page} with specific table reference in chunk")
                        return True
        
        return False

    def _filter_unique_keywords(self, keywords: List[str], chunk_content: str) -> List[str]:
        """
        Filter keywords to only include those that are relatively unique to this table.
        
        Args:
            keywords: List of keywords from table
            chunk_content: Content of the chunk
            
        Returns:
            List of keywords that are more unique/distinctive
        """
        unique_keywords = []
        
        common_financial_terms = {
            '2023', '2024', '2025', '2022', '2021',  # Years
            'million', 'billion', 'thousand',  # Scale
            'total', 'change', 'growth', 'percent', '%',  # Common metrics
            'revenue', 'sales', 'income', 'profit',  # Common financial terms
            'assets', 'equity', 'debt', 'cash'  # Balance sheet terms
        }
        
        for keyword in keywords:
            keyword_lower = keyword.lower().strip()
            
            # Skip very common terms
            if keyword_lower in common_financial_terms:
                continue
                
            # Skip pure numbers or very short terms
            if len(keyword_lower) < 4 and keyword_lower.isdigit():
                continue
                
            # Include longer, more specific terms
            if len(keyword_lower) >= 5:
                unique_keywords.append(keyword)
            # Include terms with specific patterns (like company names, specific metrics)
            elif any(char.isupper() for char in keyword):  # Has uppercase (likely proper noun)
                unique_keywords.append(keyword)
            elif keyword_lower not in chunk_content.lower().split()[:20]:
                unique_keywords.append(keyword)
        
        return unique_keywords

    def _extract_table_keywords(self, table_data: Dict[str, Any]) -> List[str]:
        """
        Extract distinctive keywords from table data for matching.
        
        Args:
            table_data: Table data from document processing
            
        Returns:
            List of distinctive keywords from the table
        """
        keywords = []
        
        if "data" not in table_data or not table_data["data"]:
            return keywords
        
        table_rows = table_data["data"]
        
        if table_rows and table_rows[0]:
            for cell in table_rows[0]:
                if cell and str(cell).strip():
                    cell_text = str(cell).strip()
                    if self._is_distinctive_table_element(cell_text):
                        keywords.append(cell_text)
        
        for row in table_rows[1:3]:
            if row:
                for cell in row:
                    if cell and str(cell).strip():
                        cell_text = str(cell).strip()
                        if self._is_distinctive_table_element(cell_text):
                            keywords.append(cell_text)
        
        return list(set(keywords))