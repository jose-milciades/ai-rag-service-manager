"""RetrievalService con el vector store en memoria y un embedder determinista."""

import base64
from typing import Any
from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.infrastructure.vector_store.vector_store_manager import VectorStoreManager
from app.schemas.retrieval import (
    ExtractTextRequest,
    IngestTextRequest,
    RetrievalDocumentRequest,
    RetrievalSearchRequest,
)
from app.services.embedding.document_embedding_service import DocumentEmbeddingService
from app.services.retrieval.retrieval_service import RetrievalService

INDEX = "project-1"


class FakeEmbedder:
    dim = 8
    model_name = "fake"

    @staticmethod
    def _vec(text: str) -> list[float]:
        vec = [0.0] * 8
        for i, ch in enumerate(text.lower()):
            vec[(ord(ch) + i) % 8] += 1.0
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


@pytest.fixture()
def storage() -> Mock:
    blobs: dict[str, bytes] = {}
    client = Mock()
    client.upload_bytes.side_effect = lambda data, name, ctype, storage_name, bucket=None: (
        blobs.__setitem__(storage_name, data) or True
    )
    client.download_from_bucket.side_effect = lambda name, bucket=None: blobs[name]
    client.blobs = blobs
    return client


@pytest.fixture()
def service(mock_settings: Settings, storage: Mock) -> RetrievalService:
    documents = DocumentEmbeddingService(
        settings=mock_settings,
        storage_client=storage,
        vector_store_manager=VectorStoreManager(mock_settings),
        embedding_provider=FakeEmbedder(),  # type: ignore[arg-type]
    )
    return RetrievalService(mock_settings, documents, storage)


def _ingest(service: RetrievalService, doc_id: str, name: str, text: str, **kw: Any) -> Any:
    return service.ingest_text(
        IngestTextRequest(indexVecstore=INDEX, idDocument=doc_id, fileName=name, text=text, **kw)
    )


def test_ingest_search_and_text(service: RetrievalService) -> None:
    result = _ingest(service, "d1", "politica.txt", "politica de privacidad " * 80)
    assert result.chunks_created >= 1 and result.text_stored
    found = service.search(RetrievalSearchRequest(indexVecstore=INDEX, query="privacidad", topK=3))
    assert found.total_results >= 1
    assert found.results[0].text and len(found.results[0].text) > 200  # chunk completo
    assert found.results[0].metadata["source"] == "text_ingestion"


def test_nin_filter_excludes_evaluation_files(service: RetrievalService) -> None:
    _ingest(service, "d1", "manual.txt", "manual de procesos internos " * 40)
    _ingest(service, "d2", "evaluacion.json", "manual de procesos internos " * 40)
    request = RetrievalSearchRequest(
        indexVecstore=INDEX,
        query="manual de procesos",
        topK=10,
        metadataFilter={"file_name": {"$nin": ["evaluacion.json"]}},
    )
    names = {r.metadata["file_name"] for r in service.search(request).results}
    assert names == {"manual.txt"}


def test_ingest_replace_removes_previous_chunks(service: RetrievalService) -> None:
    _ingest(service, "d1", "a.txt", "primera version " * 100)
    second = _ingest(service, "d1", "a.txt", "segunda version " * 10)
    assert second.deleted_count > 0
    doc = service.document(RetrievalDocumentRequest(indexVecstore=INDEX, uniqueCode="d1"))
    assert "primera" not in (doc.text or "") and "segunda" in (doc.text or "")


def test_ingest_without_replace_keeps_previous(service: RetrievalService) -> None:
    _ingest(service, "d1", "a.txt", "uno " * 50)
    again = _ingest(service, "d1", "a.txt", "dos " * 50, replace=False)
    assert again.deleted_count == 0


def test_document_range_and_order(service: RetrievalService) -> None:
    _ingest(service, "d1", "largo.txt", "palabra " * 600, chunkSize=500, chunkOverlap=100)
    full = service.document(RetrievalDocumentRequest(indexVecstore=INDEX, uniqueCode="d1"))
    assert full.total_chunks > 3
    assert [c.chunk_index for c in full.chunks] == sorted(c.chunk_index for c in full.chunks)
    part = service.document(
        RetrievalDocumentRequest(indexVecstore=INDEX, uniqueCode="d1", fromChunk=1, toChunk=2)
    )
    assert [c.chunk_index for c in part.chunks] == [1, 2]
    limited = service.document(
        RetrievalDocumentRequest(indexVecstore=INDEX, uniqueCode="d1", maxChunks=2)
    )
    assert limited.total_chunks == 2


def test_document_unknown_returns_empty(service: RetrievalService) -> None:
    doc = service.document(RetrievalDocumentRequest(indexVecstore=INDEX, uniqueCode="nope"))
    assert doc.total_chunks == 0 and doc.chunks == []


def test_expand_and_merge_context_use_stored_text(service: RetrievalService) -> None:
    text = " ".join(f"frase{i}" for i in range(400))
    _ingest(service, "d1", "texto.txt", text, chunkSize=300, chunkOverlap=50)
    found = service.search(
        RetrievalSearchRequest(
            indexVecstore=INDEX,
            query="frase10 frase11",
            topK=5,
            expandContext=True,
            mergeContext=True,
        )
    )
    assert found.results[0].expanded_text
    assert found.merged_context
    # las ventanas solapadas se funden: el contexto unido no repite el mismo tramo
    assert found.merged_context.count("frase10 ") <= 1


def test_ingest_rejects_too_large_text(service: RetrievalService, mock_settings: Settings) -> None:
    big = "x" * (mock_settings.rag_max_text_chars + 1)
    with pytest.raises(ValueError, match="demasiado grande"):
        _ingest(service, "d1", "a.txt", big)


def test_extract_text_from_base64(service: RetrievalService) -> None:
    body = base64.b64encode(b"hola mundo").decode()
    result = service.extract_text(ExtractTextRequest(fileName="a.txt", base64=body))
    assert result.text == "hola mundo" and result.characters == 10


def test_extract_text_requires_a_source(service: RetrievalService) -> None:
    with pytest.raises(ValueError):
        service.extract_text(ExtractTextRequest(fileName="a.txt"))


def test_ingest_survives_storage_failure(service: RetrievalService, storage: Mock) -> None:
    storage.upload_bytes.side_effect = RuntimeError("Bucket name is required")
    result = _ingest(service, "d9", "a.txt", "contenido de prueba " * 20)
    assert result.chunks_created >= 1 and result.text_stored is False
