"""Embedding model infrastructure adapter.

Encapsula el modelo de embeddings real detras de ``EmbeddingProvider``, que
selecciona un backend (OpenAI o local via ``sentence-transformers``) segun
``RAG_EMBEDDING_PROVIDER`` -- ver ``pendientes.md`` P-27. El resto de la app
(``RAGService``, ``DocumentEmbeddingService``) no conoce cual backend esta
activo, solo usa ``embed_documents``/``embed_query``/``dim``/``model_name``.

Cargar/inicializar un backend puede ser costoso (descarga de pesos locales, o
un cliente HTTP reusable); por eso ``EmbeddingProvider`` debe crearse una sola
vez (``@lru_cache`` en ``app/api/dependencies/services.py``) y compartirse
entre todas las colecciones/instancias de ``RAGService``, nunca recrearse por
request o por indice.
"""

import logging
from typing import Any, Protocol

from openai import OpenAI
from pymilvus.model.dense import SentenceTransformerEmbeddingFunction

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Dimension nativa de los modelos de embeddings de OpenAI soportados hoy.
# Se usa solo para exponer ``dim`` (necesario para crear la coleccion del
# vector store) sin tener que hacer una llamada real a la API en el startup;
# RAG_OPENAI_EMBEDDING_DIMENSIONS permite pedir explicitamente un valor menor
# (parametro `dimensions`, soportado solo por los modelos v3).
_OPENAI_MODEL_DIMENSIONS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
}


class _EmbeddingBackend(Protocol):
    model_name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class _LocalEmbeddingBackend:
    """Backend local via ``sentence-transformers`` (wrapper ``pymilvus.model``), sin costo ni red."""

    def __init__(self, settings: Settings) -> None:
        logger.info(
            "loading local embedding model %s on device %s",
            settings.rag_embedding_model,
            settings.rag_embedding_device,
        )
        self._function = SentenceTransformerEmbeddingFunction(
            model_name=settings.rag_embedding_model,
            device=settings.rag_embedding_device,
            normalize_embeddings=settings.rag_normalize_embeddings,
        )
        self.model_name = settings.rag_embedding_model
        self.dim = self._function.dim
        logger.info("local embedding model %s ready, dim=%s", self.model_name, self.dim)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [vector.tolist() for vector in self._function.encode_documents(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self._function.encode_queries([text])[0].tolist()


class _OpenAIEmbeddingBackend:
    """Backend real contra la API de embeddings de OpenAI."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when RAG_EMBEDDING_PROVIDER=openai")

        self.model_name = settings.rag_embedding_model
        self._requested_dimensions = settings.rag_openai_embedding_dimensions
        dim = self._requested_dimensions or _OPENAI_MODEL_DIMENSIONS.get(self.model_name)
        if dim is None:
            raise ValueError(
                f"Unknown dimension for OpenAI embedding model {self.model_name!r}; "
                "set RAG_OPENAI_EMBEDDING_DIMENSIONS explicitly."
            )
        self.dim = dim
        self._client = OpenAI(api_key=settings.openai_api_key)
        logger.info("using openai embedding model %s, dim=%s", self.model_name, self.dim)

    def _create_embeddings(self, texts: list[str]) -> list[list[float]]:
        kwargs: dict[str, Any] = {"model": self.model_name, "input": texts}
        if self._requested_dimensions is not None:
            kwargs["dimensions"] = self._requested_dimensions
        response = self._client.embeddings.create(**kwargs)
        return [item.embedding for item in response.data]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._create_embeddings(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._create_embeddings([text])[0]


class EmbeddingProvider:
    """Genera embeddings reales para texto de documentos y de consulta."""

    def __init__(self, settings: Settings) -> None:
        provider = settings.rag_embedding_provider.strip().lower()
        self._backend: _EmbeddingBackend
        if provider == "openai":
            self._backend = _OpenAIEmbeddingBackend(settings)
        elif provider == "local":
            self._backend = _LocalEmbeddingBackend(settings)
        else:
            raise ValueError(
                f"Unsupported RAG_EMBEDDING_PROVIDER={provider!r}; use 'openai' or 'local'"
            )
        self.model_name = self._backend.model_name
        self.dim = self._backend.dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para chunks de texto que se van a indexar."""
        return self._backend.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """Genera el embedding de una consulta de busqueda.

        Se mantiene separado de ``embed_documents`` porque algunos modelos
        (no los que soporta hoy este servicio, pero si otros soportados por
        ``pymilvus.model``) usan una codificacion asimetrica entre documento
        y consulta.
        """
        return self._backend.embed_query(text)
