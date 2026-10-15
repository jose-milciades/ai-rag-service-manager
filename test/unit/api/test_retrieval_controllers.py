"""Rutas /retrieval, /ingestion y /extraction (servicio simulado)."""

from collections.abc import Generator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.services import get_retrieval_service
from app.schemas.retrieval import (
    ExtractTextResponse,
    IngestTextResponse,
    RetrievalDocumentResponse,
    RetrievalSearchResponse,
)
from app.services.embedding.text_extractors import UnsupportedFormatError


@pytest.fixture()
def service_mock() -> Mock:
    svc = Mock()
    svc.search.return_value = RetrievalSearchResponse(
        index_name="project_1", query="q", total_results=0, results=[]
    )
    svc.document.return_value = RetrievalDocumentResponse(
        index_name="project_1", unique_code="x", total_chunks=0, chunks=[]
    )
    svc.ingest_text.return_value = IngestTextResponse(
        index_name="project_1", id_document="d", chunks_created=2, text_stored=True
    )
    svc.extract_text.return_value = ExtractTextResponse(
        file_name="a.txt", text="hola", characters=4
    )
    return svc


@pytest.fixture()
def client(test_app, service_mock: Mock) -> Generator[TestClient, None, None]:
    test_app.dependency_overrides[get_retrieval_service] = lambda: service_mock
    yield TestClient(test_app)
    test_app.dependency_overrides.pop(get_retrieval_service, None)


def _url(client: TestClient, path: str) -> str:
    return "/api/v1" + path


def test_search_ok_and_filter_forwarded(client: TestClient, service_mock: Mock) -> None:
    response = client.post(
        _url(client, "/retrieval/search"),
        json={
            "indexVecstore": "project-1",
            "query": "algo",
            "topK": 5,
            "metadataFilter": {"file_name": {"$nin": ["x"]}},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["indexName"] == "project_1" and body["totalResults"] == 0
    sent = service_mock.search.call_args.args[0]
    assert sent.metadata_filter == {"file_name": {"$nin": ["x"]}} and sent.include_text is True


def test_search_validates_top_k(client: TestClient) -> None:
    response = client.post(
        _url(client, "/retrieval/search"),
        json={"indexVecstore": "p", "query": "q", "topK": 500},
    )
    assert response.status_code == 422


def test_search_bad_filter_is_422(client: TestClient, service_mock: Mock) -> None:
    service_mock.search.side_effect = ValueError("Unsupported filter operator: '$regex'")
    response = client.post(
        _url(client, "/retrieval/search"), json={"indexVecstore": "p", "query": "q", "topK": 5}
    )
    assert response.status_code == 422


def test_document_ok(client: TestClient) -> None:
    response = client.post(
        _url(client, "/retrieval/document"), json={"indexVecstore": "p", "uniqueCode": "x"}
    )
    assert response.status_code == 200 and response.json()["totalChunks"] == 0


def test_ingest_text_ok(client: TestClient, service_mock: Mock) -> None:
    response = client.post(
        _url(client, "/ingestion/text"),
        json={"indexVecstore": "p", "idDocument": "d", "fileName": "n", "text": "contenido"},
    )
    assert response.status_code == 200
    assert response.json()["chunksCreated"] == 2 and response.json()["textStored"] is True
    assert service_mock.ingest_text.call_args.args[0].replace is True


def test_ingest_text_empty_is_422(client: TestClient) -> None:
    response = client.post(
        _url(client, "/ingestion/text"),
        json={"indexVecstore": "p", "idDocument": "d", "fileName": "n", "text": ""},
    )
    assert response.status_code == 422


def test_extract_text_ok(client: TestClient) -> None:
    response = client.post(
        _url(client, "/extraction/text"), json={"fileName": "a.txt", "base64": "aG9sYQ=="}
    )
    assert response.status_code == 200 and response.json()["text"] == "hola"


def test_extract_text_unsupported_is_415(client: TestClient, service_mock: Mock) -> None:
    service_mock.extract_text.side_effect = UnsupportedFormatError("no soportado")
    response = client.post(
        _url(client, "/extraction/text"), json={"fileName": "a.bin", "base64": "AA=="}
    )
    assert response.status_code == 415


def test_extract_text_missing_blob_is_404(client: TestClient, service_mock: Mock) -> None:
    service_mock.extract_text.side_effect = FileNotFoundError("nope")
    response = client.post(
        _url(client, "/extraction/text"), json={"fileName": "a.pdf", "uniqueCode": "x"}
    )
    assert response.status_code == 404
