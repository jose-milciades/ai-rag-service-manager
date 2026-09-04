"""Unit tests for all /storage/* endpoints."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.services import get_storage_service
from app.schemas.storage import (
    ChunkUploadResponse,
    FileResponse,
    UploadFileResponse,
    UploadPublicFileResponse,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage_service_mock() -> Mock:
    """Mock StorageService with async method stubs returning proper schema objects."""
    svc = Mock()
    svc.upload_file = AsyncMock(return_value=UploadFileResponse(success=True))
    svc.store_chunk = AsyncMock(return_value=ChunkUploadResponse(consolidated=False, success=True))
    svc.get_file = AsyncMock(return_value=(b"file content", "application/pdf"))
    svc.get_file_byte = AsyncMock(
        return_value=FileResponse(base64="dGVzdA==", application="text/plain")
    )
    svc.upload_public_file = AsyncMock(
        return_value=UploadPublicFileResponse(success=True, url="https://example.com/file.txt")
    )
    return svc


@pytest.fixture()
def client_with_storage(
    test_app: FastAPI, storage_service_mock: Mock
) -> Generator[TestClient, None, None]:
    test_app.dependency_overrides[get_storage_service] = lambda: storage_service_mock
    yield TestClient(test_app)
    test_app.dependency_overrides.pop(get_storage_service, None)


# ---------------------------------------------------------------------------
# upload_file  POST /storage/upload
# ---------------------------------------------------------------------------


def test_upload_file_ok(client_with_storage: TestClient, storage_service_mock: Mock) -> None:
    response = client_with_storage.post(
        "/api/v1/storage/upload",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        data={"name": "my_file"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    storage_service_mock.upload_file.assert_called_once()


def test_upload_file_missing_name_returns_422(client_with_storage: TestClient) -> None:
    """The `name` form field is required — missing it gives a 422."""
    response = client_with_storage.post(
        "/api/v1/storage/upload",
        files={"file": ("test.txt", b"content", "text/plain")},
        # `name` intentionally omitted
    )
    assert response.status_code == 422


def test_upload_file_missing_file_returns_422(client_with_storage: TestClient) -> None:
    response = client_with_storage.post(
        "/api/v1/storage/upload",
        data={"name": "my_file"},
    )
    assert response.status_code == 422


def test_upload_file_service_returns_failure(
    client_with_storage: TestClient, storage_service_mock: Mock
) -> None:
    """If the service returns success=False, the endpoint still returns 200."""
    storage_service_mock.upload_file.return_value = UploadFileResponse(success=False)
    response = client_with_storage.post(
        "/api/v1/storage/upload",
        files={"file": ("test.txt", b"content", "text/plain")},
        data={"name": "my_file"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is False


def test_upload_file_with_optional_fields(
    client_with_storage: TestClient, storage_service_mock: Mock
) -> None:
    response = client_with_storage.post(
        "/api/v1/storage/upload",
        files={"file": ("test.txt", b"content", "text/plain")},
        data={
            "name": "my_file",
            "bucket": "my-bucket",
            "projectId": "proj1",
        },
    )
    assert response.status_code == 200
    storage_service_mock.upload_file.assert_called_once()
    call_kwargs = storage_service_mock.upload_file.call_args.kwargs
    assert call_kwargs["bucket"] == "my-bucket"
    assert call_kwargs["project_id"] == "proj1"


# ---------------------------------------------------------------------------
# upload_chunk  POST /storage/chunk
# ---------------------------------------------------------------------------


def test_upload_chunk_ok(client_with_storage: TestClient, storage_service_mock: Mock) -> None:
    response = client_with_storage.post(
        "/api/v1/storage/chunk",
        files={"file": ("chunk0.bin", b"chunk_data", "application/octet-stream")},
        data={
            "uploadId": "upload123",
            "chunkIndex": "0",
            "totalChunks": "3",
            "fileName": "original.pdf",
            "name": "my_upload",
            "projectId": "proj1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["consolidated"] is False
    storage_service_mock.store_chunk.assert_called_once()


def test_upload_chunk_consolidated_response(
    client_with_storage: TestClient, storage_service_mock: Mock
) -> None:
    storage_service_mock.store_chunk.return_value = ChunkUploadResponse(
        consolidated=True, success=True
    )
    response = client_with_storage.post(
        "/api/v1/storage/chunk",
        files={"file": ("chunk2.bin", b"last_chunk", "application/octet-stream")},
        data={
            "uploadId": "upload123",
            "chunkIndex": "2",
            "totalChunks": "3",
            "fileName": "original.pdf",
            "name": "my_upload",
            "projectId": "proj1",
        },
    )
    assert response.status_code == 200
    assert response.json()["consolidated"] is True


def test_upload_chunk_missing_required_field(client_with_storage: TestClient) -> None:
    """Missing uploadId gives 422."""
    response = client_with_storage.post(
        "/api/v1/storage/chunk",
        files={"file": ("chunk0.bin", b"data", "application/octet-stream")},
        data={
            # uploadId omitted
            "chunkIndex": "0",
            "totalChunks": "3",
            "fileName": "original.pdf",
            "name": "my_upload",
            "projectId": "proj1",
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# get_file  GET /storage/get
# ---------------------------------------------------------------------------


def test_get_file_ok(client_with_storage: TestClient, storage_service_mock: Mock) -> None:
    response = client_with_storage.get(
        "/api/v1/storage/get",
        params={"name": "myfile.pdf"},
    )
    assert response.status_code == 200
    assert response.content == b"file content"
    assert "attachment" in response.headers.get("Content-Disposition", "")
    storage_service_mock.get_file.assert_called_once_with(name="myfile.pdf", bucket=None)


def test_get_file_with_bucket(client_with_storage: TestClient, storage_service_mock: Mock) -> None:
    response = client_with_storage.get(
        "/api/v1/storage/get",
        params={"name": "myfile.pdf", "bucket": "my-bucket"},
    )
    assert response.status_code == 200
    storage_service_mock.get_file.assert_called_once_with(name="myfile.pdf", bucket="my-bucket")


def test_get_file_missing_name_returns_422(client_with_storage: TestClient) -> None:
    response = client_with_storage.get("/api/v1/storage/get")
    assert response.status_code == 422


def test_get_file_not_found(client_with_storage: TestClient, storage_service_mock: Mock) -> None:
    from fastapi import HTTPException, status

    storage_service_mock.get_file.side_effect = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
    )
    response = client_with_storage.get(
        "/api/v1/storage/get",
        params={"name": "missing.pdf"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# getFileByte  GET /storage/getFileByte
# ---------------------------------------------------------------------------


def test_get_file_byte_ok(client_with_storage: TestClient, storage_service_mock: Mock) -> None:
    response = client_with_storage.get(
        "/api/v1/storage/getFileByte",
        params={"name": "myfile.txt"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["base64"] == "dGVzdA=="
    assert body["application"] == "text/plain"
    storage_service_mock.get_file_byte.assert_called_once_with(name="myfile.txt", bucket=None)


def test_get_file_byte_missing_name_returns_422(client_with_storage: TestClient) -> None:
    response = client_with_storage.get("/api/v1/storage/getFileByte")
    assert response.status_code == 422


def test_get_file_byte_with_bucket(
    client_with_storage: TestClient, storage_service_mock: Mock
) -> None:
    response = client_with_storage.get(
        "/api/v1/storage/getFileByte",
        params={"name": "myfile.txt", "bucket": "my-bucket"},
    )
    assert response.status_code == 200
    storage_service_mock.get_file_byte.assert_called_once_with(
        name="myfile.txt", bucket="my-bucket"
    )


# ---------------------------------------------------------------------------
# public-upload  POST /storage/public-upload
# ---------------------------------------------------------------------------


def test_upload_public_file_ok(client_with_storage: TestClient, storage_service_mock: Mock) -> None:
    response = client_with_storage.post(
        "/api/v1/storage/public-upload",
        files={"file": ("image.png", b"png_bytes", "image/png")},
        data={"name": "public_image"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["url"] == "https://example.com/file.txt"
    storage_service_mock.upload_public_file.assert_called_once()


def test_upload_public_file_missing_required_fields(
    client_with_storage: TestClient,
) -> None:
    """name is required, file is required."""
    response = client_with_storage.post(
        "/api/v1/storage/public-upload",
        data={"name": "public_image"},
        # file omitted
    )
    assert response.status_code == 422


def test_upload_public_file_failure_response(
    client_with_storage: TestClient, storage_service_mock: Mock
) -> None:
    storage_service_mock.upload_public_file.return_value = UploadPublicFileResponse(
        success=False, url=None
    )
    response = client_with_storage.post(
        "/api/v1/storage/public-upload",
        files={"file": ("image.png", b"png_bytes", "image/png")},
        data={"name": "public_image"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["url"] is None
