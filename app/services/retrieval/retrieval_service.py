"""Servicio de las APIs /retrieval, /ingestion y /extraction.

Compone ``DocumentEmbeddingService`` (que ya sabe extraer texto, hablar con
storage e indexar) sin modificar el contrato de las rutas ``/embedding``.
"""

import logging
from typing import Any

from app.core.config import Settings
from app.infrastructure.clients.storage_client import StorageClient
from app.schemas.retrieval import (
    ExtractTextRequest,
    ExtractTextResponse,
    IngestTextRequest,
    IngestTextResponse,
    RetrievalChunk,
    RetrievalDocumentRequest,
    RetrievalDocumentResponse,
    RetrievalResult,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from app.services.embedding.document_embedding_service import (
    TEXT_INGESTION_SOURCE,
    DocumentEmbeddingService,
)

logger = logging.getLogger(__name__)

# Claves que el cliente no puede sobrescribir via ``metadata`` al indexar texto.
_RESERVED_KEYS = {
    "file_name",
    "id_document",
    "unique_code",
    "bucket",
    "source",
    "chunk_index",
    "start_index",
    "end_index",
    "text",
}


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        documents: DocumentEmbeddingService,
        storage_client: StorageClient,
    ) -> None:
        self._settings = settings
        self._documents = documents
        self._storage_client = storage_client

    def search(self, request: RetrievalSearchRequest) -> RetrievalSearchResponse:
        rag = self._documents.rag_service_for(request.index_vecstore)
        raw = rag.search(
            query=request.query,
            top_k=request.top_k,
            filter_conditions=request.metadata_filter,
        )
        expanded = (
            self._documents.expand_results(request.index_vecstore, raw)
            if request.expand_context
            else [None] * len(raw)
        )
        results = [
            RetrievalResult(
                id=item["id"],
                score=item["score"],
                metadata={k: v for k, v in item["payload"].items() if k != "text"},
                text=item["payload"].get("text") if request.include_text else None,
                expanded_text=expanded_text,
            )
            for item, expanded_text in zip(raw, expanded)
        ]
        merged = (
            self._documents.merge_context(request.index_vecstore, raw)
            if request.merge_context
            else None
        )
        return RetrievalSearchResponse(
            index_name=request.index_vecstore,
            query=request.query,
            total_results=len(results),
            results=results,
            merged_context=merged,
        )

    def document(self, request: RetrievalDocumentRequest) -> RetrievalDocumentResponse:
        limit = min(
            request.max_chunks or self._settings.rag_max_embeddings_per_document,
            self._settings.rag_max_embeddings_per_document,
        )
        chunk_range: dict[str, Any] = {}
        if request.from_chunk > 0:
            chunk_range["$gte"] = request.from_chunk
        if request.to_chunk is not None:
            chunk_range["$lte"] = request.to_chunk
        records: list[dict[str, Any]] = []
        for key in ("unique_code", "id_document"):  # algunos documentos solo traen id_document
            conditions: dict[str, Any] = {key: request.unique_code}
            if chunk_range:
                conditions["chunk_index"] = chunk_range
            records = self._documents.list_chunk_records(request.index_vecstore, limit, conditions)
            if records:
                break
        records.sort(key=lambda r: r["payload"].get("chunk_index", 0))
        records = records[:limit]
        chunks = [
            RetrievalChunk(
                chunk_index=int(r["payload"].get("chunk_index", 0)),
                text=r["payload"].get("text", ""),
                metadata={k: v for k, v in r["payload"].items() if k != "text"},
            )
            for r in records
        ]
        return RetrievalDocumentResponse(
            index_name=request.index_vecstore,
            unique_code=request.unique_code,
            total_chunks=len(chunks),
            chunks=chunks,
            text="\n".join(c.text for c in chunks) if request.join_text else None,
        )

    def ingest_text(self, request: IngestTextRequest) -> IngestTextResponse:
        if len(request.text) > self._settings.rag_max_text_chars:
            raise ValueError(
                f"Texto demasiado grande ({len(request.text)} > {self._settings.rag_max_text_chars})"
            )
        rag = self._documents.rag_service_for(request.index_vecstore)
        deleted = 0
        if request.replace:
            deleted = rag.delete_records({"id_document": request.id_document})
        try:
            stored = self._storage_client.upload_bytes(
                request.text.encode("utf-8"), None, "text/plain", request.id_document, None
            )
        except Exception:
            # storage no disponible/configurado: se indexa igual, solo sin expandContext
            logger.exception("fallo guardando el texto de %s en storage", request.id_document)
            stored = False
        if not stored:
            logger.warning(
                "texto de %s no guardado en storage: expandContext no estara disponible",
                request.id_document,
            )
        metadata = {k: v for k, v in request.metadata.items() if k not in _RESERVED_KEYS}
        metadata.update(
            {
                "file_name": request.file_name,
                "id_document": request.id_document,
                "unique_code": request.id_document,
                "bucket": None,
                "source": TEXT_INGESTION_SOURCE,
            }
        )
        created = rag.index_documents(
            documents=[request.text],
            metadata=[metadata],
            chunk=True,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
        )
        return IngestTextResponse(
            index_name=request.index_vecstore,
            id_document=request.id_document,
            chunks_created=created,
            deleted_count=deleted,
            text_stored=stored,
        )

    def extract_text(self, request: ExtractTextRequest) -> ExtractTextResponse:
        if not (request.base64 or request.url_download_file or request.unique_code):
            raise ValueError("Se requiere base64, urlDownloadFile o uniqueCode")
        content = self._documents.load_file(
            request.file_name,
            request.base64,
            request.url_download_file,
            request.bucket,
            request.unique_code,
        )
        text = self._documents.extract_text(
            content, request.file_name, request.unique_code, request.bucket
        )
        return ExtractTextResponse(file_name=request.file_name, text=text, characters=len(text))
