"""Embedding model infrastructure adapter.

Encapsula el modelo de embeddings real detras de ``EmbeddingProvider``, que
habla contra la API de OpenAI -- unico proveedor soportado (decision de
negocio, ver ``pendientes.md`` P-19; el backend local via
``sentence-transformers``/``torch`` que existia antes fue removido del todo
para bajar el tamano de la imagen Docker). El resto de la app (``RAGService``,
``DocumentEmbeddingService``) no conoce el detalle de la API, solo usa
``embed_documents``/``embed_query``/``dim``/``model_name``.

``EmbeddingProvider`` mantiene un cliente HTTP reusable; por eso debe crearse
una sola vez (``@lru_cache`` en ``app/api/dependencies/services.py``) y
compartirse entre todas las colecciones/instancias de ``RAGService``, nunca
recrearse por request o por indice.
"""

import logging
from typing import Any

from openai import OpenAI

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


class EmbeddingProvider:
    """Genera embeddings reales para texto de documentos y de consulta, via OpenAI."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required")

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
        """Genera embeddings para chunks de texto que se van a indexar."""
        if not texts:
            return []
        return self._create_embeddings(texts)

    def embed_query(self, text: str) -> list[float]:
        """Genera el embedding de una consulta de busqueda."""
        return self._create_embeddings([text])[0]
