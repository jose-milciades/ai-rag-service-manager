"""Core RAG retrieval service.

Este modulo contiene la logica central de indexacion y recuperacion semantica.
No conoce HTTP y no depende de controllers. Trabaja sobre una abstraccion de
vector store para que la infraestructura pueda cambiar sin romper el contrato.

El embedding real (modelo cargado una sola vez) vive en ``EmbeddingProvider``
y se inyecta aqui; ``RAGService`` no sabe que libreria concreta lo genera.
"""

import re
from typing import Any

from app.core.config import Settings
from app.infrastructure.embeddings.embedding_provider import EmbeddingProvider
from app.infrastructure.vector_store.vector_store_manager import VectorStoreManager

# re.ASCII: sin este flag, \W tambien dejaria pasar letras unicode (acentos,
# otros alfabetos) por ser "word chars" en Python -- Milvus exige ASCII puro.
_INVALID_COLLECTION_CHARS = re.compile(r"\W", re.ASCII)


def _sanitize_collection_name(name: str) -> str:
    """Milvus solo acepta letras, numeros y guion bajo en nombres de coleccion
    (ver pendientes.md P-25 -- encontrado probando P-10 contra Milvus real:
    ``project-42`` es un nombre valido en el backend en memoria pero invalido
    en Milvus). Cualquier otro caracter (guiones, espacios, puntos, etc.) se
    reemplaza por "_"; si el resultado queda vacio o empieza con un digito
    (tambien invalido en Milvus), se le antepone un guion bajo.
    """
    sanitized = _INVALID_COLLECTION_CHARS.sub("_", name)
    if not sanitized:
        return "_"
    if sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    return sanitized


def _resolve_collection_name(prefix: str, collection_name: str) -> str:
    cleaned_name = _sanitize_collection_name(collection_name)
    cleaned_prefix = _sanitize_collection_name(prefix.strip()) if prefix.strip() else ""
    if not cleaned_prefix:
        return cleaned_name
    if cleaned_name == cleaned_prefix or cleaned_name.startswith(f"{cleaned_prefix}_"):
        return cleaned_name
    return f"{cleaned_prefix}_{cleaned_name}"


class RAGService:
    """Servicio central para chunking, embedding, indexacion y retrieval."""

    def __init__(
        self,
        settings: Settings,
        vector_store_manager: VectorStoreManager,
        embedding_provider: EmbeddingProvider,
        collection_name: str | None = None,
    ) -> None:
        self._settings = settings
        self._vector_store = vector_store_manager
        self._embedding_provider = embedding_provider
        self.collection_name = _resolve_collection_name(
            settings.rag_collection_name_prefix,
            collection_name or settings.rag_default_collection_name,
        )
        self.embedding_model = embedding_provider.model_name
        self._vector_size = embedding_provider.dim
        if not self._vector_store.collection_exists(self.collection_name):
            self._vector_store.create_collection(
                self.collection_name, vector_size=self._vector_size
            )

    def index_documents(
        self,
        documents: list[str],
        metadata: list[dict[str, Any]] | None = None,
        chunk: bool = True,
    ) -> int:
        """Indexa documentos completos o sus chunks en la coleccion activa."""
        metadata = metadata or [{} for _ in documents]
        texts_to_index: list[str] = []
        metadata_to_index: list[dict[str, Any]] = []

        for document, meta in zip(documents, metadata):
            chunks = self._split_text(document) if chunk else [document]
            for chunk_index, current_chunk in enumerate(chunks):
                texts_to_index.append(current_chunk)
                metadata_to_index.append(
                    {**meta, "chunk_index": chunk_index, "text": current_chunk}
                )

        vectors = self._embedding_provider.embed_documents(texts_to_index)
        self._vector_store.insert_vectors(
            self.collection_name, vectors=vectors, payloads=metadata_to_index
        )
        return len(texts_to_index)

    def search(
        self,
        query: str,
        top_k: int | None = None,
        filter_conditions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Busca chunks similares a una consulta dentro de la coleccion activa."""
        effective_top_k = top_k or self._settings.rag_default_top_k
        return self._vector_store.search(
            collection_name=self.collection_name,
            query_vector=self._embedding_provider.embed_query(query),
            top_k=effective_top_k,
            filter_conditions=filter_conditions,
        )

    def clear_collection(self) -> None:
        """Elimina completamente la coleccion vectorial actual."""
        self._vector_store.delete_collection(self.collection_name)

    def delete_records(self, filter_conditions: dict[str, Any]) -> int:
        """Elimina registros de la coleccion activa que cumplan el filtro indicado."""
        return self._vector_store.delete_records(self.collection_name, filter_conditions)

    def _split_text(self, text: str) -> list[str]:
        """Divide un texto en chunks usando tamano y overlap configurados."""
        chunk_size = max(self._settings.rag_chunk_size, 1)
        overlap = min(self._settings.rag_chunk_overlap, chunk_size - 1) if chunk_size > 1 else 0
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = end - overlap
        return chunks or [text]
