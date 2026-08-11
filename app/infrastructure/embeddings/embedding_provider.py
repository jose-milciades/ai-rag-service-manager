"""Embedding model infrastructure adapter.

Encapsula el modelo de embeddings real (sentence-transformers, cargado via el
wrapper de ``pymilvus.model``) para que ``RAGService`` no dependa directamente
de la libreria concreta. Cargar el modelo es costoso (descarga/lectura de
pesos a memoria); por eso ``EmbeddingProvider`` debe crearse una sola vez
(``@lru_cache`` en ``app/api/dependencies/services.py``) y compartirse entre
todas las colecciones/instancias de ``RAGService``, nunca recrearse por
request o por indice.
"""

import logging

from pymilvus.model.dense import SentenceTransformerEmbeddingFunction

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """Genera embeddings reales para texto de documentos y de consulta."""

    def __init__(self, settings: Settings) -> None:
        logger.info(
            "loading embedding model %s on device %s",
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
        logger.info("embedding model %s ready, dim=%s", self.model_name, self.dim)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para chunks de texto que se van a indexar."""
        if not texts:
            return []
        return [vector.tolist() for vector in self._function.encode_documents(texts)]

    def embed_query(self, text: str) -> list[float]:
        """Genera el embedding de una consulta de busqueda.

        Se mantiene separado de ``embed_documents`` porque algunos modelos
        (no este por defecto, pero si otros soportados por
        ``pymilvus.model``) usan una codificacion asimetrica entre
        documento y consulta.
        """
        return self._function.encode_queries([text])[0].tolist()
