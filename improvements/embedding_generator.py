"""
Azure OpenAI Embedding Generator Module

This module provides a component for generating document embeddings
using Azure OpenAI services.

Features:
• Class-based design with proper encapsulation
• Configurable embedding models and parameters
• Error handling and retry mechanisms
• Performance monitoring and logging

Usage:
    # Create embedding configuration
    config = EmbeddingConfig(
        endpoint=<endpoint>,
        api_key=<api-key>,
        deployment=<deployment>,
        model=<model>
    )
    
    generator = EmbeddingGeneratorFactory.create_azure_openai_generator(config, logger_name=<logger_name>)
    
    results = await generator.embed_document_chunks(document_id, chunks)

Author:
    Tirso Gomez

Version:
    1.0.0
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain.docstore.document import Document
from langchain_openai import AzureOpenAIEmbeddings

from custom_logging import AppLogger


@dataclass
class EmbeddingConfig:
    """    
    This class encapsulates all configuration parameters needed for
    Azure OpenAI embedding generation.
    """
    endpoint: str
    api_key: str
    deployment: str
    model: str
    api_version: str
    dimensions: int
    batch_size: int
    max_retries: int
    retry_delay: float
    timeout: int
    show_progress_bar: Optional[bool] = None
    tiktoken_enabled: Optional[bool] = None
    
    def __post_init__(self):
        """Validate configuration parameters after initialization."""
        required_str_params = {
            "endpoint": "Azure OpenAI endpoint is required",
            "api_key": "Azure OpenAI API key is required",
            "deployment": "Azure OpenAI deployment name is required",
            "api_version": "Azure OpenAI API version is required",
            "model": "Azure OpenAI model name is required"
        }
        
        required_numeric_params = {
            "dimensions": "Embedding dimensions are required",
            "batch_size": "Batch size is required",
            "max_retries": "Max retries are required",
            "retry_delay": "Retry delay is required",
            "timeout": "Timeout is required"
        }
        
        for param, error_msg in required_str_params.items():
            if not getattr(self, param):
                raise ValueError(error_msg)
        
        for param, error_msg in required_numeric_params.items():
            value = getattr(self, param)
            if not value:
                raise ValueError(error_msg)
        
        if self.dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive")
        if self.batch_size <= 0:
            raise ValueError("Batch size must be positive")


class AzureOpenAIEmbeddingGenerator:
    """
    This class provides embedding generation using Azure OpenAI services
    with error handling, retry logic, and performance monitoring.
    """
    
    def __init__(self, config: EmbeddingConfig, logger_name: str):
        """
        Initialize the Azure OpenAI embedding generator.
        
        Args:
            config: Configuration for the embedding generator
            logger_name: Name for the logger instance
        """
        self.config = config
        self.logger = AppLogger(logger_name=logger_name, level="DEBUG")
        self._embeddings_model = None
        self._initialize_model()
    
    def _initialize_model(self) -> None:
        """Initialize the Azure OpenAI embeddings model."""
        try:
            self.logger.info("Initializing Azure OpenAI embeddings model")
            
            self._embeddings_model = AzureOpenAIEmbeddings(
                model=self.config.model,
                azure_endpoint=self.config.endpoint,
                api_key=self.config.api_key,
                dimensions=self.config.dimensions,
                azure_deployment=self.config.deployment,
                api_version=self.config.api_version,
                openai_api_type="azure",
                show_progress_bar=self.config.show_progress_bar,
                tiktoken_enabled=self.config.tiktoken_enabled
            )
            
            self.logger.info(f"Successfully initialized embeddings model: {self.config.model}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize embeddings model: {str(e)}")
            raise
    
    @property
    def embeddings_model(self) -> AzureOpenAIEmbeddings:
        """
        Get the embeddings model instance.
        
        Returns:
            AzureOpenAIEmbeddings: The initialized embeddings model
        """
        if self._embeddings_model is None:
            self._initialize_model()
        return self._embeddings_model
    
    async def embed_document_chunks(
        self, 
        document_id: str, 
        chunks: List[Document],
        storage: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for document chunks.
        
        Args:
            document_id: ID of the document whose chunks to embed
            chunks: List of document chunks
            storage: Optional storage instance
            
        Returns:
            List[Dict[str, Any]]: Results of embedding generation in legacy format
        """
        self.logger.info(f"Generating embeddings for document: {document_id}")
        
        if not chunks:
            self.logger.warning(f"No chunks provided for document ID: {document_id}")
            return []
        
        results = []
        total_chunks = len(chunks)
        total_retries = 0
        
        self.logger.info(f"Processing {total_chunks} chunks for document {document_id}")
        
        for i, chunk in enumerate(chunks):
            try:
                start_time = time.time()
                
                embedding_vector, chunk_retries = await self._embed_text_with_metrics(chunk.page_content)
                total_retries += chunk_retries
                
                embedding_time = time.time() - start_time
                chunk_id = chunk.metadata.get("chunk_id", f"{document_id}_chunk_{i}")
                
                word_count = len(chunk.page_content.split())
                char_count = len(chunk.page_content)
                
                estimated_tokens_words = int(word_count * 0.75)
                estimated_tokens_chars = char_count // 4
                estimated_tokens = max(estimated_tokens_words, estimated_tokens_chars)
                
                result = {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "text": chunk.page_content,
                    "embedding": embedding_vector,
                    "metadata": chunk.metadata.copy(),
                    "embedding_time": embedding_time,
                    "estimated_tokens": estimated_tokens,
                    "retry_count": chunk_retries,
                    "chunk_index": i
                }
                
                results.append(result)
                self.logger.debug(f"Generated embedding for chunk {i+1}/{total_chunks} in {embedding_time:.3f} seconds (retries: {chunk_retries})")
                
            except Exception as e:
                self.logger.error(f"Error generating embedding for chunk {i}: {str(e)}")
                continue
        
        successful_count = len(results)
        self.logger.info(f"Successfully generated {successful_count}/{total_chunks} embeddings for document {document_id} (total retries: {total_retries})")
        
        return results
    
    async def _embed_text_with_metrics(self, text: str) -> tuple[List[float], int]:
        """
        Generate embedding for a single text string with retry metrics
        
        Args:
            text: Text to embed
            
        Returns:
            tuple: (embedding vector, retry count)
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        retry_count = 0
        
        for attempt in range(self.config.max_retries):
            try:
                start_time = time.time()
                embedding = self.embeddings_model.embed_query(text)
                embedding_time = time.time() - start_time
                
                self.logger.debug(f"Generated embedding in {embedding_time:.3f} seconds (attempt {attempt + 1})")
                return embedding, retry_count
                
            except Exception as e:
                retry_count += 1
                self.logger.warning(f"Embedding attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    self.logger.error(f"Failed to generate embedding after {self.config.max_retries} attempts")
                    raise


class EmbeddingGeneratorFactory:
    """Factory class for creating embedding generators."""
    
    @staticmethod
    def create_azure_openai_generator(
        config: EmbeddingConfig,
        logger_name: str
    ) -> AzureOpenAIEmbeddingGenerator:
        """
        Create an Azure OpenAI embedding generator.
        
        Args:
            config: Configuration for the generator
            logger_name: Name for the logger
            
        Returns:
            AzureOpenAIEmbeddingGenerator: Configured generator instance
        """
        return AzureOpenAIEmbeddingGenerator(config, logger_name)