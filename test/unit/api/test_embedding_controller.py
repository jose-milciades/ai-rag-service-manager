"""Unit tests for all POST /embedding/* endpoints."""

from collections.abc import Generator
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.services import get_document_embedding_service

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def embedding_service_mock() -> Mock:
    """Mock DocumentEmbeddingService with return values matching real shapes."""
    svc = Mock()
    svc.save_document_to_vecstore.return_value = {
        "success": True,
        "message": "Document indexed successfully",
        "unique_code": "abc123",
        "chunks_created": 5,
        "index_name": "my_collection",
    }
    svc.delete_index.return_value = {
        "success": True,
        "message": "Index 'my_collection' deleted successfully",
        "index_name": "my_collection",
    }
    svc.delete_document.return_value = {
        "success": True,
        "message": "Document deleted",
        "index_name": "my_collection",
        "id_document": "doc123",
        "deleted_count": 2,
    }
    svc.list_unique_code_documents.return_value = [
        {
            "namespace": "my_collection",
            "codigo": "abc123",
            "file_name": "test.txt",
            "id": "1",
            "nombre_documento": "test.txt",
        }
    ]
    svc.list_documents_by_index.return_value = {
        "success": True,
        "index_name": "my_collection",
        "total_results": 1,
        "documents": [],
    }
    svc.get_embeddings_by_unique_code.return_value = {
        "success": True,
        "unique_code": "abc123",
        "index_name": "my_collection",
        "total_chunks": 2,
        "embeddings": [],
    }
    svc.search_similar_documents.return_value = {
        "success": True,
        "query": "search term",
        "index_name": "my_collection",
        "total_results": 1,
        "results": [],
    }
    return svc


@pytest.fixture()
def client_with_embedding(
    test_app: FastAPI, embedding_service_mock: Mock
) -> Generator[TestClient, None, None]:
    test_app.dependency_overrides[get_document_embedding_service] = lambda: embedding_service_mock
    yield TestClient(test_app)
    test_app.dependency_overrides.pop(get_document_embedding_service, None)


# ---------------------------------------------------------------------------
# save_document_vecstore
# ---------------------------------------------------------------------------

_SAVE_PAYLOAD = {
    "fileName": "test.txt",
    "base64": "dGVzdA==",
    "idDocument": "doc123",
    "indexVecstore": "my_collection",
    "uniqueCode": "abc123",
    "hasDocumentBase64": True,
    "listParameters": [],
}


def test_save_document_vecstore_ok(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/save_document_vecstore",
        json=_SAVE_PAYLOAD,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["uniqueCode"] == "abc123"
    assert body["chunksCreated"] == 5
    assert body["indexName"] == "my_collection"
    embedding_service_mock.save_document_to_vecstore.assert_called_once()


def test_save_document_vecstore_missing_required_fields(
    client_with_embedding: TestClient,
) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/save_document_vecstore",
        json={},
    )
    assert response.status_code == 422


def test_save_document_vecstore_service_raises(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    embedding_service_mock.save_document_to_vecstore.side_effect = RuntimeError("DB error")
    response = client_with_embedding.post(
        "/api/v1/embedding/save_document_vecstore",
        json=_SAVE_PAYLOAD,
    )
    assert response.status_code == 500
    assert "Error saving document" in response.json()["detail"]


def test_save_document_snake_case_also_works(
    client_with_embedding: TestClient,
) -> None:
    """populate_by_name=True means snake_case keys are also accepted."""
    response = client_with_embedding.post(
        "/api/v1/embedding/save_document_vecstore",
        json={
            "file_name": "test.txt",
            "base64": "dGVzdA==",
            "id_document": "doc123",
            "index_vecstore": "my_collection",
            "unique_code": "abc123",
            "has_document_base64": True,
            "list_parameters": [],
        },
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# delete_index_vecstore (background task)
# ---------------------------------------------------------------------------


def test_delete_index_schedules_background_task(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    """TestClient runs background tasks synchronously before returning."""
    response = client_with_embedding.post(
        "/api/v1/embedding/delete_index_vecstore",
        json={"indexVecstore": "my_collection"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "my_collection" in body["mensaje"]
    assert body["codigo"] == 200
    # Background task ran synchronously inside TestClient
    embedding_service_mock.delete_index.assert_called_once_with("my_collection")


def test_delete_index_missing_required_field(client_with_embedding: TestClient) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/delete_index_vecstore",
        json={},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------


def test_delete_document_ok(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/delete_document",
        json={"indexVecstore": "my_collection", "idDocument": "doc123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["idDocument"] == "doc123"
    assert body["deletedCount"] == 2
    embedding_service_mock.delete_document.assert_called_once_with(
        index_name="my_collection",
        id_document="doc123",
    )


def test_delete_document_missing_required_fields(client_with_embedding: TestClient) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/delete_document",
        json={},
    )
    assert response.status_code == 422


def test_delete_document_service_raises(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    embedding_service_mock.delete_document.side_effect = ValueError("not found")
    response = client_with_embedding.post(
        "/api/v1/embedding/delete_document",
        json={"indexVecstore": "my_collection", "idDocument": "doc123"},
    )
    assert response.status_code == 500
    assert "Error deleting document" in response.json()["detail"]


# ---------------------------------------------------------------------------
# list_unique_code_documents
# ---------------------------------------------------------------------------


def test_list_unique_code_documents_ok(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/list_unique_code_documents",
        # Body is a raw JSON string (plain string, not an object)
        content=b'"my_collection"',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["codigo"] == "abc123"
    embedding_service_mock.list_unique_code_documents.assert_called_once_with(
        namespace="my_collection"
    )


def test_list_unique_code_documents_service_raises(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    embedding_service_mock.list_unique_code_documents.side_effect = RuntimeError("fail")
    response = client_with_embedding.post(
        "/api/v1/embedding/list_unique_code_documents",
        content=b'"my_collection"',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 500
    assert "Error listing unique code documents" in response.json()["detail"]


# ---------------------------------------------------------------------------
# list_documents
# ---------------------------------------------------------------------------


def test_list_documents_ok(client_with_embedding: TestClient, embedding_service_mock: Mock) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/list_documents",
        json={"indexVecstore": "my_collection"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["indexName"] == "my_collection"
    assert body["totalResults"] == 1
    embedding_service_mock.list_documents_by_index.assert_called_once()


def test_list_documents_missing_required_field(client_with_embedding: TestClient) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/list_documents",
        json={},
    )
    assert response.status_code == 422


def test_list_documents_service_raises(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    embedding_service_mock.list_documents_by_index.side_effect = RuntimeError("storage fail")
    response = client_with_embedding.post(
        "/api/v1/embedding/list_documents",
        json={"indexVecstore": "my_collection"},
    )
    assert response.status_code == 500
    assert "Error listing documents" in response.json()["detail"]


# ---------------------------------------------------------------------------
# get_embeddings_by_unique_code
# ---------------------------------------------------------------------------


def test_get_embeddings_by_unique_code_ok(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/get_embeddings_by_unique_code",
        json={"indexVecstore": "my_collection", "uniqueCode": "abc123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["uniqueCode"] == "abc123"
    assert body["totalChunks"] == 2
    embedding_service_mock.get_embeddings_by_unique_code.assert_called_once_with(
        index_name="my_collection",
        unique_code="abc123",
    )


def test_get_embeddings_by_unique_code_missing_fields(
    client_with_embedding: TestClient,
) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/get_embeddings_by_unique_code",
        json={},
    )
    assert response.status_code == 422


def test_get_embeddings_by_unique_code_service_raises(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    embedding_service_mock.get_embeddings_by_unique_code.side_effect = RuntimeError("db err")
    response = client_with_embedding.post(
        "/api/v1/embedding/get_embeddings_by_unique_code",
        json={"indexVecstore": "my_collection", "uniqueCode": "abc123"},
    )
    assert response.status_code == 500
    assert "Error getting embeddings" in response.json()["detail"]


# ---------------------------------------------------------------------------
# search_similar_documents
# ---------------------------------------------------------------------------


def test_search_similar_documents_ok(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/search_similar_documents",
        json={"indexVecstore": "my_collection", "query": "search term"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["query"] == "search term"
    assert body["totalResults"] == 1
    embedding_service_mock.search_similar_documents.assert_called_once()


def test_search_similar_documents_missing_fields(client_with_embedding: TestClient) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/search_similar_documents",
        json={},
    )
    assert response.status_code == 422


def test_search_similar_documents_service_raises(
    client_with_embedding: TestClient, embedding_service_mock: Mock
) -> None:
    embedding_service_mock.search_similar_documents.side_effect = RuntimeError("vec fail")
    response = client_with_embedding.post(
        "/api/v1/embedding/search_similar_documents",
        json={"indexVecstore": "my_collection", "query": "search term"},
    )
    assert response.status_code == 500
    assert "Error searching documents" in response.json()["detail"]


def test_search_similar_documents_with_optional_fields(
    client_with_embedding: TestClient,
) -> None:
    response = client_with_embedding.post(
        "/api/v1/embedding/search_similar_documents",
        json={
            "indexVecstore": "my_collection",
            "query": "search term",
            "topK": 3,
            "metadataFilter": {"author": "alice"},
            "expandContext": True,
        },
    )
    assert response.status_code == 200
