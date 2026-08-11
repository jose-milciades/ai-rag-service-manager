"""Core RAG retrieval service.

Este modulo contiene la logica central de indexacion y recuperacion semantica.
No conoce HTTP y no depende de controllers. Trabaja sobre una abstraccion de
vector store para que la infraestructura pueda cambiar sin romper el contrato.

En esta version el embedding es liviano y deterministico para mantener el
microservicio autocontenido. La interfaz queda lista para reemplazar ese motor
por embeddings reales mas adelante.
"""

import hashlib
import math
import re
from typing import Any

from app.core.config import Settings
from app.infrastructure.vector_store.vector_store_manager import VectorStoreManager


def _resolve_collection_name(prefix: str, collection_name: str) -> str:
    cleaned_prefix = prefix.strip()
    if not cleaned_prefix:
        return collection_name
    if collection_name == cleaned_prefix or collection_name.startswith(f"{cleaned_prefix}_"):
        return collection_name
    return f"{cleaned_prefix}_{collection_name}"


class RAGService:
    """Servicio central para chunking, embedding, indexacion y retrieval."""

    def __init__(
        self,
        settings: Settings,
        vector_store_manager: VectorStoreManager,
        collection_name: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        self._settings = settings
        self._vector_store = vector_store_manager
        self.collection_name = _resolve_collection_name(
            settings.rag_collection_name_prefix,
            collection_name or settings.rag_default_collection_name,
        )
        self.embedding_model = embedding_model or settings.rag_embedding_model
        self._vector_size = 128
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

        vectors = [self._embed_text(text) for text in texts_to_index]
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
            query_vector=self._embed_text(query),
            top_k=effective_top_k,
            filter_conditions=filter_conditions,
        )

    def retrieve_context(
        self,
        query: str,
        top_k: int | None = None,
        filter_conditions: dict[str, Any] | None = None,
    ) -> str:
        """Convierte resultados de retrieval en un bloque de contexto legible."""
        results = self.search(query=query, top_k=top_k, filter_conditions=filter_conditions)
        context_parts = []
        for index, result in enumerate(results, start=1):
            context_parts.append(
                f"[Document {index}] (relevance: {result['score']:.3f})\n{result['payload'].get('text', '')}\n"
            )
        return "\n".join(context_parts)

    def answer_question(
        self,
        question: str,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        """Entrega contexto y fuentes para una pregunta cuando aun no hay LLM integrado."""
        context = self.retrieve_context(question, top_k=top_k)
        return {
            "answer": "No LLM client provided. Returning retrieved context.",
            "context": context,
            "sources": self.search(question, top_k=top_k),
        }

    def clear_collection(self) -> None:
        """Elimina completamente la coleccion vectorial actual."""
        self._vector_store.delete_collection(self.collection_name)

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

    def _embed_text(self, text: str) -> list[float]:
        """Genera un embedding deterministico y liviano para el texto recibido."""
        vector = [0.0] * self._vector_size
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self._vector_size
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]
