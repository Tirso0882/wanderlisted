"""Embedding generator with batch support and retry logic.

Wraps any LangChain ``Embeddings`` backend with:

* ``EmbeddingConfig`` dataclass for Azure-specific settings (legacy)
* Provider-agnostic path via ``get_embeddings()`` factory
* Batch ``embed_documents()`` with exponential backoff (handles 429s)
* Per-batch timing and retry metrics
"""

import os
import time
from dataclasses import dataclass
from typing import Optional

from langchain_core.embeddings import Embeddings as BaseEmbeddings

from custom_logging import AppLogger


@dataclass
class EmbeddingConfig:
    """All parameters needed for Azure OpenAI embeddings, loadable from env."""

    endpoint: str = ""
    api_key: str = ""
    deployment: str = ""
    api_version: str = ""
    dimensions: int = 3072
    batch_size: int = 100
    max_retries: int = 5
    retry_delay: float = 2.0

    def __post_init__(self):
        required = {
            "endpoint": self.endpoint,
            "api_key": self.api_key,
            "deployment": self.deployment,
            "api_version": self.api_version,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing required EmbeddingConfig fields: {missing}")
        if self.dimensions <= 0:
            raise ValueError("dimensions must be positive")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """Build config from standard Wanderlisted environment variables."""
        return cls(
            endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
            deployment=os.environ.get("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", ""),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", ""),
            dimensions=int(os.environ.get("EMBEDDING_DIMENSION", "3072")),
            batch_size=int(os.environ.get("EMBEDDING_BATCH_SIZE", "100")),
        )


class EmbeddingGenerator:
    """Batch embedding generator with retry / backoff for any LangChain embeddings backend."""

    def __init__(
        self,
        config: Optional[EmbeddingConfig] = None,
        *,
        model: Optional[BaseEmbeddings] = None,
        logger_name: str = "rag.embeddings",
        batch_size: int = 100,
        max_retries: int = 5,
        retry_delay: float = 2.0,
    ):
        """Initialise with either an explicit model, an Azure config, or auto-detect.

        Priority: model > config > get_embeddings() factory.
        """
        self.logger = AppLogger(logger_name=logger_name, level="DEBUG")

        if model is not None:
            # Caller passed a ready-to-use embeddings object
            self._model = model
            self._batch_size = batch_size
            self._max_retries = max_retries
            self._retry_delay = retry_delay
        elif config is not None:
            # Legacy Azure-specific config path
            self._batch_size = config.batch_size
            self._max_retries = config.max_retries
            self._retry_delay = config.retry_delay
            self._model = self._build_azure_model(config)
        else:
            # Provider-agnostic: use the central factory
            from src.agent.llm import get_embeddings

            self._model = get_embeddings()
            self._batch_size = batch_size
            self._max_retries = max_retries
            self._retry_delay = retry_delay

    @staticmethod
    def _build_azure_model(config: EmbeddingConfig) -> BaseEmbeddings:
        from langchain_openai import AzureOpenAIEmbeddings

        return AzureOpenAIEmbeddings(
            azure_deployment=config.deployment,
            azure_endpoint=config.endpoint,
            api_key=config.api_key,
            api_version=config.api_version,
        )

    @property
    def model(self) -> BaseEmbeddings:
        return self._model

    # ── Single query embedding ───────────────────────────────────────────

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (used at search time)."""
        return self.model.embed_query(text)

    # ── Batch document embedding with retry ──────────────────────────────

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts in batches, retrying on transient errors."""
        all_vectors: list[list[float]] = []
        total = len(texts)
        batch_size = self._batch_size
        total_retries = 0

        for start in range(0, total, batch_size):
            batch = texts[start : start + batch_size]
            vectors, retries = self._embed_batch_with_retry(batch)
            all_vectors.extend(vectors)
            total_retries += retries

            if start + batch_size < total:
                self.logger.debug(
                    f"  Embedded {start + len(batch)}/{total} "
                    f"(retries so far: {total_retries})"
                )

        self.logger.info(
            f"Embedded {total} texts in {(total + batch_size - 1) // batch_size} "
            f"batch(es), {total_retries} total retries"
        )
        return all_vectors

    def _embed_batch_with_retry(
        self, texts: list[str]
    ) -> tuple[list[list[float]], int]:
        """Embed one batch with exponential backoff on failure."""
        retries = 0
        for attempt in range(self._max_retries):
            try:
                t0 = time.time()
                vectors = self.model.embed_documents(texts)
                elapsed = time.time() - t0
                self.logger.debug(
                    f"  Batch ({len(texts)} texts) embedded in {elapsed:.2f}s"
                )
                return vectors, retries
            except Exception as e:
                retries += 1
                delay = self._retry_delay * (2**attempt)
                self.logger.warning(
                    f"  Embed attempt {attempt + 1} failed: {e} — "
                    f"retrying in {delay:.1f}s"
                )
                if attempt < self._max_retries - 1:
                    time.sleep(delay)
                else:
                    self.logger.error(f"  Failed after {self._max_retries} attempts")
                    raise
        # unreachable but keeps mypy happy
        raise RuntimeError("embed retry loop exited unexpectedly")
