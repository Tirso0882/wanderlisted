"""Tests for src/rag/embeddings.py — EmbeddingConfig + EmbeddingGenerator."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.rag.embeddings import EmbeddingConfig, EmbeddingGenerator


# ── EmbeddingConfig ──────────────────────────────────────────────────────

class TestEmbeddingConfig:
    def test_valid_config(self):
        cfg = EmbeddingConfig(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="text-embedding-3-large",
            api_version="2024-02-01",
            dimensions=3072,
            batch_size=100,
        )
        assert cfg.dimensions == 3072

    def test_missing_endpoint_raises(self):
        with pytest.raises(ValueError, match="endpoint"):
            EmbeddingConfig(
                endpoint="",
                api_key="key",
                deployment="dep",
                api_version="v1",
            )

    def test_missing_api_key_raises(self):
        with pytest.raises(ValueError, match="api_key"):
            EmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="",
                deployment="dep",
                api_version="v1",
            )

    def test_zero_dimensions_raises(self):
        with pytest.raises(ValueError, match="dimensions"):
            EmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="key",
                deployment="dep",
                api_version="v1",
                dimensions=0,
            )

    def test_zero_batch_size_raises(self):
        with pytest.raises(ValueError, match="batch_size"):
            EmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="key",
                deployment="dep",
                api_version="v1",
                batch_size=0,
            )

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "text-embedding-3-large")
        monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

        cfg = EmbeddingConfig.from_env()
        assert cfg.endpoint == "https://test.openai.azure.com"
        assert cfg.deployment == "text-embedding-3-large"
        assert cfg.dimensions == 3072  # default

    def test_from_env_custom_dimensions(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "dep")
        monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "v1")
        monkeypatch.setenv("EMBEDDING_DIMENSION", "1536")

        cfg = EmbeddingConfig.from_env()
        assert cfg.dimensions == 1536


# ── EmbeddingGenerator ───────────────────────────────────────────────────

class TestEmbeddingGenerator:
    @patch("langchain_openai.AzureOpenAIEmbeddings")
    def test_embed_query(self, mock_cls):
        mock_model = MagicMock()
        mock_model.embed_query.return_value = [0.1] * 3072
        mock_cls.return_value = mock_model

        cfg = EmbeddingConfig(
            endpoint="https://test.openai.azure.com",
            api_key="key",
            deployment="dep",
            api_version="v1",
        )
        gen = EmbeddingGenerator(config=cfg, logger_name="test.emb")
        result = gen.embed_query("hello")

        assert len(result) == 3072
        mock_model.embed_query.assert_called_once_with("hello")

    @patch("langchain_openai.AzureOpenAIEmbeddings")
    def test_embed_documents_batches(self, mock_cls):
        mock_model = MagicMock()
        mock_model.embed_documents.return_value = [[0.1] * 3072] * 2
        mock_cls.return_value = mock_model

        cfg = EmbeddingConfig(
            endpoint="https://test.openai.azure.com",
            api_key="key",
            deployment="dep",
            api_version="v1",
            batch_size=2,
        )
        gen = EmbeddingGenerator(config=cfg, logger_name="test.emb")
        texts = ["a", "b", "c", "d"]
        result = gen.embed_documents(texts)

        assert len(result) == 4
        # Should have been called twice (2 batches of 2)
        assert mock_model.embed_documents.call_count == 2

    @patch("langchain_openai.AzureOpenAIEmbeddings")
    @patch("src.rag.embeddings.time.sleep")
    def test_retry_on_failure(self, mock_sleep, mock_cls):
        mock_model = MagicMock()
        # Fail first call, succeed second
        mock_model.embed_documents.side_effect = [
            Exception("429 rate limit"),
            [[0.1] * 3072],
        ]
        mock_cls.return_value = mock_model

        cfg = EmbeddingConfig(
            endpoint="https://test.openai.azure.com",
            api_key="key",
            deployment="dep",
            api_version="v1",
            max_retries=3,
            retry_delay=0.01,
        )
        gen = EmbeddingGenerator(config=cfg, logger_name="test.emb")
        result = gen.embed_documents(["hello"])

        assert len(result) == 1
        assert mock_model.embed_documents.call_count == 2
        mock_sleep.assert_called_once()

    @patch("langchain_openai.AzureOpenAIEmbeddings")
    @patch("src.rag.embeddings.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep, mock_cls):
        mock_model = MagicMock()
        mock_model.embed_documents.side_effect = Exception("persistent error")
        mock_cls.return_value = mock_model

        cfg = EmbeddingConfig(
            endpoint="https://test.openai.azure.com",
            api_key="key",
            deployment="dep",
            api_version="v1",
            max_retries=2,
            retry_delay=0.01,
        )
        gen = EmbeddingGenerator(config=cfg, logger_name="test.emb")

        with pytest.raises(Exception, match="persistent error"):
            gen.embed_documents(["hello"])
