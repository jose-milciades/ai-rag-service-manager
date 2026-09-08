"""Tests for app/schemas/embedding.py and app/schemas/storage.py."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.schemas.embedding import (
    DeleteDocumentVecstoreResponse,
    DocumentSummaryResponse,
    OperationStatusResponse,
    SaveDocumentVecstoreRequest,
    SaveDocumentVecstoreResponse,
    SearchSimilarDocumentsRequest,
)
from app.schemas.storage import (
    ChunkUploadResponse,
    FileResponse,
    UploadFileResponse,
    UploadPublicFileResponse,
)

# ---------------------------------------------------------------------------
# SaveDocumentVecstoreRequest
# ---------------------------------------------------------------------------


_SAVE_DOC_REQUIRED = {
    "fileName": "doc.pdf",
    "idDocument": "abc-123",
    "indexVecstore": "my_index",
    "uniqueCode": "uc-001",
}


def test_save_document_vecstore_request_camel_case_deserialization() -> None:
    """camelCase keys are accepted and mapped to snake_case attributes."""
    req = SaveDocumentVecstoreRequest(**_SAVE_DOC_REQUIRED)
    assert req.file_name == "doc.pdf"
    assert req.id_document == "abc-123"
    assert req.index_vecstore == "my_index"
    assert req.unique_code == "uc-001"


def test_save_document_vecstore_request_snake_case_deserialization() -> None:
    """snake_case keys also work because populate_by_name=True."""
    req = SaveDocumentVecstoreRequest(
        file_name="doc.pdf",
        id_document="abc-123",
        index_vecstore="my_index",
        unique_code="uc-001",
    )
    assert req.index_vecstore == "my_index"


def test_save_document_vecstore_request_optional_fields_default_none() -> None:
    """base64, url_download_file, and bucket are optional (None by default)."""
    req = SaveDocumentVecstoreRequest(**_SAVE_DOC_REQUIRED)
    assert req.base64 is None
    assert req.url_download_file is None
    assert req.bucket is None


def test_save_document_vecstore_request_has_document_base64_default_true() -> None:
    """has_document_base64 defaults to True."""
    req = SaveDocumentVecstoreRequest(**_SAVE_DOC_REQUIRED)
    assert req.has_document_base64 is True


def test_save_document_vecstore_request_list_parameters_default_empty() -> None:
    """list_parameters defaults to an empty list."""
    req = SaveDocumentVecstoreRequest(**_SAVE_DOC_REQUIRED)
    assert req.list_parameters == []


# ---------------------------------------------------------------------------
# ListDocumentsRequest — bounds (avoid default_factory lru_cache issues)
# ---------------------------------------------------------------------------


def _make_list_documents_request(**kwargs):  # type: ignore[no-untyped-def]
    """Helper that imports and constructs ListDocumentsRequest with explicit limit."""
    from app.schemas.embedding import ListDocumentsRequest

    return ListDocumentsRequest(**kwargs)


def test_list_documents_request_limit_minimum_valid() -> None:
    """limit=1 is valid (ge=1)."""
    req = _make_list_documents_request(index_vecstore="idx", limit=1)
    assert req.limit == 1


def test_list_documents_request_limit_below_minimum_raises() -> None:
    """limit=0 is below ge=1 — must raise ValidationError."""
    with pytest.raises(ValidationError):
        _make_list_documents_request(index_vecstore="idx", limit=0)


def test_list_documents_request_limit_maximum_valid() -> None:
    """limit=1000 is valid (le=1000)."""
    req = _make_list_documents_request(index_vecstore="idx", limit=1000)
    assert req.limit == 1000


def test_list_documents_request_limit_above_maximum_raises() -> None:
    """limit=1001 exceeds le=1000 — must raise ValidationError."""
    with pytest.raises(ValidationError):
        _make_list_documents_request(index_vecstore="idx", limit=1001)


def test_list_documents_request_limit_default_from_settings(mock_settings) -> None:  # type: ignore[no-untyped-def]
    """Default limit comes from get_settings().rag_default_list_limit."""
    mock_settings.rag_default_list_limit = 42
    with patch("app.schemas.embedding.get_settings", return_value=mock_settings):
        from app.schemas.embedding import ListDocumentsRequest

        req = ListDocumentsRequest(index_vecstore="idx")
        assert req.limit == 42


# ---------------------------------------------------------------------------
# SearchSimilarDocumentsRequest — bounds
# ---------------------------------------------------------------------------


def _make_search_request(**kwargs):  # type: ignore[no-untyped-def]
    from app.schemas.embedding import SearchSimilarDocumentsRequest as SR

    return SR(**kwargs)


def test_search_similar_documents_request_top_k_minimum_valid() -> None:
    req = _make_search_request(index_vecstore="idx", query="q", top_k=1)
    assert req.top_k == 1


def test_search_similar_documents_request_top_k_below_minimum_raises() -> None:
    with pytest.raises(ValidationError):
        _make_search_request(index_vecstore="idx", query="q", top_k=0)


def test_search_similar_documents_request_top_k_maximum_valid() -> None:
    req = _make_search_request(index_vecstore="idx", query="q", top_k=100)
    assert req.top_k == 100


def test_search_similar_documents_request_top_k_above_maximum_raises() -> None:
    with pytest.raises(ValidationError):
        _make_search_request(index_vecstore="idx", query="q", top_k=101)


def test_search_similar_documents_request_expand_context_default_false() -> None:
    req = SearchSimilarDocumentsRequest(index_vecstore="idx", query="q", top_k=5)
    assert req.expand_context is False


# ---------------------------------------------------------------------------
# OperationStatusResponse — Spanish field names (no camelCase change)
# ---------------------------------------------------------------------------


def test_operation_status_response_field_names() -> None:
    """mensaje and codigo are the actual field names (short, not transformed)."""
    resp = OperationStatusResponse(mensaje="ok", codigo=200)
    assert resp.mensaje == "ok"
    assert resp.codigo == 200


def test_operation_status_response_serializes_by_alias() -> None:
    """model_dump(by_alias=True) keeps 'mensaje' and 'codigo' unchanged."""
    resp = OperationStatusResponse(mensaje="ok", codigo=200)
    dumped = resp.model_dump(by_alias=True)
    assert dumped["mensaje"] == "ok"
    assert dumped["codigo"] == 200


# ---------------------------------------------------------------------------
# SaveDocumentVecstoreResponse — camelCase alias
# ---------------------------------------------------------------------------


def test_save_document_vecstore_response_chunks_created_camel_case() -> None:
    """chunks_created serializes to 'chunksCreated' by alias."""
    resp = SaveDocumentVecstoreResponse(
        success=True,
        message="done",
        unique_code="uc-001",
        chunks_created=5,
        index_name="my_index",
    )
    dumped = resp.model_dump(by_alias=True)
    assert "chunksCreated" in dumped
    assert dumped["chunksCreated"] == 5


# ---------------------------------------------------------------------------
# DeleteDocumentVecstoreResponse — camelCase alias
# ---------------------------------------------------------------------------


def test_delete_document_vecstore_response_deleted_count_camel_case() -> None:
    """deleted_count serializes to 'deletedCount' by alias."""
    resp = DeleteDocumentVecstoreResponse(
        success=True,
        message="deleted",
        index_name="my_index",
        id_document="doc-1",
        deleted_count=3,
    )
    dumped = resp.model_dump(by_alias=True)
    assert "deletedCount" in dumped
    assert dumped["deletedCount"] == 3


# ---------------------------------------------------------------------------
# DocumentSummaryResponse — optional expanded_text
# ---------------------------------------------------------------------------


def test_document_summary_response_expanded_text_default_none() -> None:
    """expanded_text is None by default."""
    resp = DocumentSummaryResponse(id="d1", text_preview="preview")
    assert resp.expanded_text is None


# ---------------------------------------------------------------------------
# UploadFileResponse
# ---------------------------------------------------------------------------


def test_upload_file_response_has_success_field() -> None:
    resp = UploadFileResponse(success=True)
    assert resp.success is True


def test_upload_file_response_false() -> None:
    resp = UploadFileResponse(success=False)
    assert resp.success is False


# ---------------------------------------------------------------------------
# ChunkUploadResponse
# ---------------------------------------------------------------------------


def test_chunk_upload_response_fields() -> None:
    resp = ChunkUploadResponse(consolidated=True, success=True)
    assert resp.consolidated is True
    assert resp.success is True


def test_chunk_upload_response_not_consolidated() -> None:
    resp = ChunkUploadResponse(consolidated=False, success=True)
    assert resp.consolidated is False


# ---------------------------------------------------------------------------
# FileResponse — all optional fields
# ---------------------------------------------------------------------------


def test_file_response_all_fields_none_by_default() -> None:
    """All FileResponse fields are optional and default to None."""
    resp = FileResponse()
    assert resp.array_bytes is None
    assert resp.application is None
    assert resp.extension is None
    assert resp.name is None
    assert resp.base64 is None


# ---------------------------------------------------------------------------
# UploadPublicFileResponse
# ---------------------------------------------------------------------------


def test_upload_public_file_response_success_and_url() -> None:
    resp = UploadPublicFileResponse(success=True, url="https://example.com/file.pdf")
    assert resp.success is True
    assert resp.url == "https://example.com/file.pdf"


def test_upload_public_file_response_url_optional() -> None:
    resp = UploadPublicFileResponse(success=False)
    assert resp.url is None
