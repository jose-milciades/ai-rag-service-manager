"""Unit tests for EmbeddingProvider (openai client mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.infrastructure.embeddings.embedding_provider import (
    _OPENAI_MODEL_DIMENSIONS,
    EmbeddingProvider,
)


def make_settings(**kwargs: object) -> Settings:
    defaults: dict[str, object] = {
        "RAG_ENVIRONMENT": "edi-local",
        "RAG_EMBEDDING_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test",
        "RAG_EMBEDDING_MODEL": "text-embedding-3-small",
        "DEBUG": False,
    }
    defaults.update(kwargs)
    return Settings(**defaults)


def make_provider(settings: Settings) -> EmbeddingProvider:
    """Construct an EmbeddingProvider with the OpenAI client mocked."""
    with patch("app.infrastructure.embeddings.embedding_provider.OpenAI"):
        return EmbeddingProvider(settings)


# ---------------------------------------------------------------------------
# __init__ — validation
# ---------------------------------------------------------------------------


class TestEmbeddingProviderInit:
    def test_missing_api_key_raises_value_error(self) -> None:
        settings = make_settings(OPENAI_API_KEY=None)
        with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
            EmbeddingProvider(settings)

    def test_known_model_uses_dimension_from_table(self) -> None:
        for model, expected_dim in _OPENAI_MODEL_DIMENSIONS.items():
            settings = make_settings(RAG_EMBEDDING_MODEL=model)
            provider = make_provider(settings)
            assert provider.dim == expected_dim, f"Wrong dim for {model}"

    def test_unknown_model_without_explicit_dimensions_raises(self) -> None:
        settings = make_settings(
            RAG_EMBEDDING_MODEL="text-embedding-unknown-v99",
            RAG_OPENAI_EMBEDDING_DIMENSIONS="",  # empty → None via validator
        )
        with (
            patch("app.infrastructure.embeddings.embedding_provider.OpenAI"),
            pytest.raises(ValueError, match="Unknown dimension"),
        ):
            EmbeddingProvider(settings)

    def test_unknown_model_with_explicit_dimensions_uses_explicit_value(self) -> None:
        settings = make_settings(
            RAG_EMBEDDING_MODEL="text-embedding-custom-v1",
            RAG_OPENAI_EMBEDDING_DIMENSIONS=512,
        )
        provider = make_provider(settings)
        assert provider.dim == 512


# ---------------------------------------------------------------------------
# embed_documents
# ---------------------------------------------------------------------------


class TestEmbedDocuments:
    def _make_mock_response(self, embeddings: list[list[float]]) -> MagicMock:
        """Build a fake openai embeddings response object."""
        items = []
        for emb in embeddings:
            item = MagicMock()
            item.embedding = emb
            items.append(item)
        response = MagicMock()
        response.data = items
        return response

    def test_empty_list_returns_empty_without_api_call(self) -> None:
        settings = make_settings()
        provider = make_provider(settings)
        provider._client.embeddings.create = MagicMock()

        result = provider.embed_documents([])
        assert result == []
        provider._client.embeddings.create.assert_not_called()

    def test_non_empty_list_calls_api_and_extracts_embeddings(self) -> None:
        settings = make_settings()
        provider = make_provider(settings)
        expected = [[0.1, 0.2, 0.3]]
        provider._client.embeddings.create.return_value = self._make_mock_response(expected)

        result = provider.embed_documents(["hello"])
        assert result == expected
        provider._client.embeddings.create.assert_called_once()

    def test_dimensions_param_added_when_requested_dimensions_set(self) -> None:
        settings = make_settings(RAG_OPENAI_EMBEDDING_DIMENSIONS=256)
        provider = make_provider(settings)
        provider._client.embeddings.create.return_value = self._make_mock_response([[0.1]])

        provider.embed_documents(["text"])
        call_kwargs = provider._client.embeddings.create.call_args.kwargs
        assert call_kwargs.get("dimensions") == 256

    def test_dimensions_param_absent_when_requested_dimensions_not_set(self) -> None:
        settings = make_settings(RAG_OPENAI_EMBEDDING_DIMENSIONS=None)
        provider = make_provider(settings)
        provider._client.embeddings.create.return_value = self._make_mock_response([[0.1]])

        provider.embed_documents(["text"])
        call_kwargs = provider._client.embeddings.create.call_args.kwargs
        assert "dimensions" not in call_kwargs


# ---------------------------------------------------------------------------
# embed_query
# ---------------------------------------------------------------------------


class TestEmbedQuery:
    def test_embed_query_returns_first_embedding(self) -> None:
        settings = make_settings()
        provider = make_provider(settings)
        expected = [0.5, 0.6, 0.7]
        response = MagicMock()
        item = MagicMock()
        item.embedding = expected
        response.data = [item]
        provider._client.embeddings.create.return_value = response

        result = provider.embed_query("what is the answer?")
        assert result == expected

    def test_embed_query_calls_api_with_single_item_list(self) -> None:
        settings = make_settings()
        provider = make_provider(settings)
        response = MagicMock()
        item = MagicMock()
        item.embedding = [0.1]
        response.data = [item]
        provider._client.embeddings.create.return_value = response

        provider.embed_query("test")
        call_kwargs = provider._client.embeddings.create.call_args.kwargs
        assert call_kwargs["input"] == ["test"]
