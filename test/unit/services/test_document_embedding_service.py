"""Unit tests for app.services.embedding.document_embedding_service."""

import base64
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.core.config import Settings
from app.infrastructure.vector_store.vector_store_manager import VectorStoreManager
from app.services.embedding.document_embedding_service import DocumentEmbeddingService

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_service(
    mock_settings: Settings,
    storage_client: Mock | None = None,
    vsm: Mock | None = None,
    emb: Mock | None = None,
) -> DocumentEmbeddingService:
    if vsm is None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.list_records.return_value = []
        vsm.delete_records.return_value = 0
    if emb is None:
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        emb.embed_documents.return_value = [[0.1] * 1536]
        emb.embed_query.return_value = [0.1] * 1536
    if storage_client is None:
        storage_client = Mock()
        storage_client.download_from_bucket.return_value = b"hello world"
        storage_client.download_from_url.return_value = b"hello world"
    return DocumentEmbeddingService(
        settings=mock_settings,
        storage_client=storage_client,
        vector_store_manager=vsm,
        embedding_provider=emb,
    )


@pytest.fixture()
def svc(mock_settings: Settings) -> DocumentEmbeddingService:
    return _make_service(mock_settings)


# ---------------------------------------------------------------------------
# _get_rag_service
# ---------------------------------------------------------------------------


class TestGetRagService:
    def test_same_index_returns_cached_instance(self, mock_settings: Settings) -> None:
        service = _make_service(mock_settings)
        first = service._get_rag_service("my_index")
        second = service._get_rag_service("my_index")
        assert first is second

    def test_different_index_creates_new_instance(self, mock_settings: Settings) -> None:
        service = _make_service(mock_settings)
        first = service._get_rag_service("index_a")
        second = service._get_rag_service("index_b")
        assert first is not second


# ---------------------------------------------------------------------------
# save_document_to_vecstore
# ---------------------------------------------------------------------------


class TestSaveDocumentToVecstore:
    def _b64(self, text: str) -> str:
        return base64.b64encode(text.encode()).decode()

    def test_base64_path_decodes_and_indexes(self, mock_settings: Settings) -> None:
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        emb.embed_documents.return_value = [[0.1] * 1536]
        sc = Mock()
        service = _make_service(mock_settings, storage_client=sc, emb=emb)

        result = service.save_document_to_vecstore(
            file_name="doc.txt",
            base64_content=self._b64("some text content"),
            id_document="doc1",
            index_name="idx",
            unique_code="uc1",
            has_document_base64=True,
        )
        # storage client NOT called for base64 path
        sc.download_from_bucket.assert_not_called()
        sc.download_from_url.assert_not_called()
        assert result["success"] is True
        assert result["unique_code"] == "uc1"
        assert result["chunks_created"] >= 1

    def test_url_path_calls_download_from_url(self, mock_settings: Settings) -> None:
        sc = Mock()
        sc.download_from_url.return_value = b"url content text"
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        emb.embed_documents.return_value = [[0.1] * 1536]
        service = _make_service(mock_settings, storage_client=sc, emb=emb)

        service.save_document_to_vecstore(
            file_name="doc.txt",
            base64_content=None,
            id_document="doc1",
            index_name="idx",
            unique_code="uc1",
            url_download_file="http://example.com/doc.txt",
            has_document_base64=False,
        )
        sc.download_from_url.assert_called_once_with("http://example.com/doc.txt")

    def test_bucket_path_calls_download_from_bucket(self, mock_settings: Settings) -> None:
        sc = Mock()
        sc.download_from_bucket.return_value = b"bucket content text"
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        emb.embed_documents.return_value = [[0.1] * 1536]
        service = _make_service(mock_settings, storage_client=sc, emb=emb)

        service.save_document_to_vecstore(
            file_name="doc.txt",
            base64_content=None,
            id_document="doc1",
            index_name="idx",
            unique_code="uc1",
            has_document_base64=False,
            bucket="my-bucket",
        )
        sc.download_from_bucket.assert_called_once_with("doc.txt", "my-bucket")

    def test_no_text_extracted_raises_value_error(self, mock_settings: Settings) -> None:
        sc = Mock()
        sc.download_from_bucket.return_value = b"   "  # whitespace only
        service = _make_service(mock_settings, storage_client=sc)

        with pytest.raises(ValueError, match="No text content"):
            service.save_document_to_vecstore(
                file_name="doc.txt",
                base64_content=None,
                id_document="doc1",
                index_name="idx",
                unique_code="uc1",
                has_document_base64=False,
            )

    def test_list_parameters_normalization_key_value(self, mock_settings: Settings) -> None:
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        emb.embed_documents.return_value = [[0.1] * 1536]
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        service = _make_service(mock_settings, emb=emb, vsm=vsm)

        service.save_document_to_vecstore(
            file_name="doc.txt",
            base64_content=base64.b64encode(b"hello world").decode(),
            id_document="doc1",
            index_name="idx",
            unique_code="uc1",
            has_document_base64=True,
            list_parameters=[{"key": "my_param", "value": "my_value"}],
        )
        payloads = vsm.insert_vectors.call_args.kwargs["payloads"]
        assert payloads[0]["my_param"] == "my_value"

    def test_list_parameters_normalization_code_value(self, mock_settings: Settings) -> None:
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        emb.embed_documents.return_value = [[0.1] * 1536]
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        service = _make_service(mock_settings, emb=emb, vsm=vsm)

        service.save_document_to_vecstore(
            file_name="doc.txt",
            base64_content=base64.b64encode(b"hello world").decode(),
            id_document="doc1",
            index_name="idx",
            unique_code="uc1",
            has_document_base64=True,
            list_parameters=[{"code": "my_code_param", "value": "code_value"}],
        )
        payloads = vsm.insert_vectors.call_args.kwargs["payloads"]
        assert payloads[0]["my_code_param"] == "code_value"

    def test_vector_chunk_size_parameter_used(self, mock_settings: Settings) -> None:
        """VECTOR_CHUNK_SIZE from parameters controls actual chunking."""
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        # With chunk_size=5, "hello world" (11 chars) → 3 chunks
        emb.embed_documents.return_value = [[0.1] * 1536] * 3
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        service = _make_service(mock_settings, emb=emb, vsm=vsm)

        result = service.save_document_to_vecstore(
            file_name="doc.txt",
            base64_content=base64.b64encode(b"hello world").decode(),
            id_document="doc1",
            index_name="idx",
            unique_code="uc1",
            has_document_base64=True,
            list_parameters=[
                {"key": "VECTOR_CHUNK_SIZE", "value": "5"},
                {"key": "VECTOR_CHUNK_OVERLAP", "value": "0"},
            ],
        )
        assert result["chunks_created"] == 3

    def test_invalid_chunk_size_falls_back_to_none(self, mock_settings: Settings) -> None:
        """Invalid VECTOR_CHUNK_SIZE string → falls back to settings default."""
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        emb.embed_documents.return_value = [[0.1] * 1536]
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        service = _make_service(mock_settings, emb=emb, vsm=vsm)

        # Should not raise; invalid int string → parsed as None → uses default
        result = service.save_document_to_vecstore(
            file_name="doc.txt",
            base64_content=base64.b64encode(b"hello world").decode(),
            id_document="doc1",
            index_name="idx",
            unique_code="uc1",
            has_document_base64=True,
            list_parameters=[{"key": "VECTOR_CHUNK_SIZE", "value": "not_a_number"}],
        )
        assert result["success"] is True


# ---------------------------------------------------------------------------
# delete_index
# ---------------------------------------------------------------------------


class TestDeleteIndex:
    def test_calls_clear_collection_and_removes_cache(self, mock_settings: Settings) -> None:
        service = _make_service(mock_settings)
        # Populate cache
        service._get_rag_service("my_index")
        assert "my_index" in service._rag_services

        result = service.delete_index("my_index")
        assert result["success"] is True
        assert "my_index" not in service._rag_services


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------


class TestDeleteDocument:
    def test_filters_by_id_document_and_returns_deleted_count(
        self, mock_settings: Settings
    ) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.delete_records.return_value = 2
        service = _make_service(mock_settings, vsm=vsm)

        result = service.delete_document("my_index", "doc1")
        assert result["deleted_count"] == 2
        assert result["id_document"] == "doc1"
        vsm.delete_records.assert_called_once()


# ---------------------------------------------------------------------------
# list_unique_code_documents
# ---------------------------------------------------------------------------


class TestListUniqueCodeDocuments:
    def test_deduplicates_by_unique_code(self, mock_settings: Settings) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.list_records.return_value = [
            {"id": "r1", "payload": {"unique_code": "uc1", "file_name": "f1.txt"}},
            {"id": "r2", "payload": {"unique_code": "uc1", "file_name": "f1.txt"}},
            {"id": "r3", "payload": {"unique_code": "uc2", "file_name": "f2.txt"}},
        ]
        service = _make_service(mock_settings, vsm=vsm)
        docs = service.list_unique_code_documents("my_ns")
        assert len(docs) == 2
        codes = {d["codigo"] for d in docs}
        assert codes == {"uc1", "uc2"}

    def test_falls_back_to_id_document_when_no_unique_code(self, mock_settings: Settings) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.list_records.return_value = [
            {"id": "r1", "payload": {"id_document": "id_doc_1", "file_name": "f.txt"}},
        ]
        service = _make_service(mock_settings, vsm=vsm)
        docs = service.list_unique_code_documents("ns")
        assert docs[0]["codigo"] == "id_doc_1"


# ---------------------------------------------------------------------------
# list_documents_by_index
# ---------------------------------------------------------------------------


class TestListDocumentsByIndex:
    def test_deduplicates_by_document_key_and_respects_limit(self, mock_settings: Settings) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.list_records.return_value = [
            {
                "id": "r1",
                "payload": {
                    "unique_code": "uc1",
                    "text": "chunk 1 text",
                    "file_name": "f.txt",
                },
            },
            {
                "id": "r2",
                "payload": {
                    "unique_code": "uc1",
                    "text": "chunk 2 text",
                    "file_name": "f.txt",
                },
            },
            {
                "id": "r3",
                "payload": {
                    "unique_code": "uc2",
                    "text": "other text",
                    "file_name": "g.txt",
                },
            },
        ]
        service = _make_service(mock_settings, vsm=vsm)
        result = service.list_documents_by_index("idx", limit=1)
        assert result["total_results"] == 1

    def test_text_excluded_from_metadata(self, mock_settings: Settings) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.list_records.return_value = [
            {
                "id": "r1",
                "payload": {
                    "unique_code": "uc1",
                    "text": "some text content",
                    "file_name": "f.txt",
                },
            },
        ]
        service = _make_service(mock_settings, vsm=vsm)
        result = service.list_documents_by_index("idx", limit=10)
        doc = result["documents"][0]
        assert "text" not in doc["metadata"]
        assert doc["text_preview"] == "some text content"[:200]


# ---------------------------------------------------------------------------
# get_embeddings_by_unique_code
# ---------------------------------------------------------------------------


class TestGetEmbeddingsByUniqueCode:
    def test_records_sorted_by_chunk_index(self, mock_settings: Settings) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.list_records.return_value = [
            {
                "id": "r3",
                "payload": {
                    "unique_code": "uc1",
                    "chunk_index": 2,
                    "text": "third",
                },
            },
            {
                "id": "r1",
                "payload": {
                    "unique_code": "uc1",
                    "chunk_index": 0,
                    "text": "first",
                },
            },
            {
                "id": "r2",
                "payload": {
                    "unique_code": "uc1",
                    "chunk_index": 1,
                    "text": "second",
                },
            },
        ]
        service = _make_service(mock_settings, vsm=vsm)
        result = service.get_embeddings_by_unique_code("idx", "uc1")
        indices = [e["chunk_index"] for e in result["embeddings"]]
        assert indices == [0, 1, 2]


# ---------------------------------------------------------------------------
# search_similar_documents
# ---------------------------------------------------------------------------


class TestSearchSimilarDocuments:
    def _make_search_svc(self, mock_settings: Settings) -> DocumentEmbeddingService:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.search.return_value = [
            {
                "id": "r1",
                "score": 0.95,
                "payload": {"text": "result text", "unique_code": "uc1"},
            }
        ]
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        emb.embed_query.return_value = [0.1] * 1536
        return _make_service(mock_settings, vsm=vsm, emb=emb)

    def test_expand_context_false_no_expanded_text(self, mock_settings: Settings) -> None:
        service = self._make_search_svc(mock_settings)
        result = service.search_similar_documents("idx", "query", top_k=5, expand_context=False)
        assert result["success"] is True
        for r in result["results"]:
            assert "expanded_text" not in r

    def test_expand_context_true_calls_expand(self, mock_settings: Settings) -> None:
        service = self._make_search_svc(mock_settings)
        with patch.object(service, "_expand_context") as mock_expand:
            result = service.search_similar_documents("idx", "query", top_k=5, expand_context=True)
            mock_expand.assert_called_once()
        assert result["success"] is True


# ---------------------------------------------------------------------------
# _load_file_content
# ---------------------------------------------------------------------------


class TestLoadFileContent:
    def test_base64_flag_true_with_content_decodes(self, mock_settings: Settings) -> None:
        sc = Mock()
        service = _make_service(mock_settings, storage_client=sc)
        content = b"binary content"
        encoded = base64.b64encode(content).decode()
        result = service._load_file_content(
            file_name="f.bin",
            base64_content=encoded,
            url_download_file=None,
            has_document_base64=True,
            bucket=None,
        )
        assert result == content
        sc.download_from_url.assert_not_called()
        sc.download_from_bucket.assert_not_called()

    def test_base64_flag_true_but_none_falls_to_url(self, mock_settings: Settings) -> None:
        sc = Mock()
        sc.download_from_url.return_value = b"url bytes"
        service = _make_service(mock_settings, storage_client=sc)
        result = service._load_file_content(
            file_name="f.txt",
            base64_content=None,
            url_download_file="http://example.com/f.txt",
            has_document_base64=True,
            bucket=None,
        )
        assert result == b"url bytes"
        sc.download_from_url.assert_called_once_with("http://example.com/f.txt")

    def test_url_present_calls_download_from_url(self, mock_settings: Settings) -> None:
        sc = Mock()
        sc.download_from_url.return_value = b"downloaded"
        service = _make_service(mock_settings, storage_client=sc)
        result = service._load_file_content(
            file_name="f.txt",
            base64_content=None,
            url_download_file="http://example.com/file.txt",
            has_document_base64=False,
            bucket=None,
        )
        assert result == b"downloaded"
        sc.download_from_url.assert_called_once()

    def test_no_base64_no_url_calls_download_from_bucket(self, mock_settings: Settings) -> None:
        sc = Mock()
        sc.download_from_bucket.return_value = b"from bucket"
        service = _make_service(mock_settings, storage_client=sc)
        result = service._load_file_content(
            file_name="myfile.txt",
            base64_content=None,
            url_download_file=None,
            has_document_base64=False,
            bucket="my-bucket",
        )
        assert result == b"from bucket"
        sc.download_from_bucket.assert_called_once_with("myfile.txt", "my-bucket")


# ---------------------------------------------------------------------------
# _extract_text_from_file
# ---------------------------------------------------------------------------


class TestExtractTextFromFile:
    def test_txt_decoded(self) -> None:
        result = DocumentEmbeddingService._extract_text_from_file(b"hello world", "doc.txt")
        assert result == "hello world"

    def test_json_decoded(self) -> None:
        result = DocumentEmbeddingService._extract_text_from_file(b'{"key": "value"}', "data.json")
        assert result == '{"key": "value"}'

    def test_md_decoded(self) -> None:
        result = DocumentEmbeddingService._extract_text_from_file(b"# Title", "readme.md")
        assert result == "# Title"

    def test_pdf_calls_pdfplumber(self) -> None:
        with patch("app.services.embedding.document_embedding_service.pdfplumber") as mock_pdf:
            mock_page = Mock()
            mock_page.extract_text.return_value = "extracted text"
            mock_pdf_obj = MagicMock()
            mock_pdf_obj.__enter__ = Mock(return_value=mock_pdf_obj)
            mock_pdf_obj.__exit__ = Mock(return_value=False)
            mock_pdf_obj.pages = [mock_page]
            mock_pdf.open.return_value = mock_pdf_obj

            result = DocumentEmbeddingService._extract_text_from_file(b"%PDF-1.4", "doc.pdf")
        assert result == "extracted text"

    def test_unknown_extension_utf8_decode(self) -> None:
        result = DocumentEmbeddingService._extract_text_from_file(b"raw text bytes", "doc.xyz")
        assert result == "raw text bytes"


# ---------------------------------------------------------------------------
# _normalize_parameters
# ---------------------------------------------------------------------------


class TestNormalizeParameters:
    def test_key_value_form(self) -> None:
        result = DocumentEmbeddingService._normalize_parameters(
            [{"key": "mykey", "value": "myval"}]
        )
        assert result == {"mykey": "myval"}

    def test_code_value_form(self) -> None:
        result = DocumentEmbeddingService._normalize_parameters(
            [{"code": "VECTOR_CHUNK_SIZE", "value": "1000"}]
        )
        assert result == {"VECTOR_CHUNK_SIZE": "1000"}

    def test_fallback_uses_update(self) -> None:
        result = DocumentEmbeddingService._normalize_parameters(
            [{"arbitrary_key": "v1", "another": "v2"}]
        )
        assert result == {"arbitrary_key": "v1", "another": "v2"}

    def test_empty_list(self) -> None:
        result = DocumentEmbeddingService._normalize_parameters([])
        assert result == {}


# ---------------------------------------------------------------------------
# _parse_int_parameter
# ---------------------------------------------------------------------------


class TestParseIntParameter:
    def test_valid_int_string(self) -> None:
        result = DocumentEmbeddingService._parse_int_parameter({"SIZE": "500"}, "SIZE")
        assert result == 500

    def test_invalid_string_returns_none(self) -> None:
        result = DocumentEmbeddingService._parse_int_parameter({"SIZE": "abc"}, "SIZE")
        assert result is None

    def test_missing_key_returns_none(self) -> None:
        result = DocumentEmbeddingService._parse_int_parameter({}, "SIZE")
        assert result is None

    def test_none_value_returns_none(self) -> None:
        result = DocumentEmbeddingService._parse_int_parameter({"SIZE": None}, "SIZE")
        assert result is None


# ---------------------------------------------------------------------------
# _expand_context
# ---------------------------------------------------------------------------


class TestExpandContext:
    def test_exception_on_one_result_does_not_affect_others(self, mock_settings: Settings) -> None:
        service = _make_service(mock_settings)
        raw_results = [
            {"id": "r1", "payload": {"unique_code": "uc1", "chunk_index": 0}},
            {"id": "r2", "payload": {"unique_code": "uc2", "chunk_index": 0}},
        ]
        formatted_results: list[dict[str, Any]] = [
            {"id": "r1", "score": 0.9, "text_preview": "text1"},
            {"id": "r2", "score": 0.8, "text_preview": "text2"},
        ]

        call_count = 0

        def side_effect(idx: str, payload: dict, cache: dict) -> str | None:
            nonlocal call_count
            call_count += 1
            if payload.get("unique_code") == "uc1":
                raise RuntimeError("expansion error")
            return "expanded for uc2"

        with patch.object(service, "_expand_single_result", side_effect=side_effect):
            service._expand_context("idx", raw_results, formatted_results)

        assert call_count == 2
        # r1 had exception → no expanded_text; r2 got expanded
        assert "expanded_text" not in formatted_results[0]
        assert formatted_results[1]["expanded_text"] == "expanded for uc2"


# ---------------------------------------------------------------------------
# _expand_single_result
# ---------------------------------------------------------------------------


class TestExpandSingleResult:
    def test_reslice_strategy_when_start_end_index_present(self, mock_settings: Settings) -> None:
        service = _make_service(mock_settings)
        payload = {
            "unique_code": "uc1",
            "file_name": "f.txt",
            "start_index": 5,
            "end_index": 10,
            "bucket": None,
        }
        with patch.object(
            service, "_expand_via_source_reslice", return_value="resliced"
        ) as mock_reslice:
            result = service._expand_single_result("idx", payload, {})
        mock_reslice.assert_called_once()
        assert result == "resliced"

    def test_adjacent_strategy_when_no_start_index(self, mock_settings: Settings) -> None:
        service = _make_service(mock_settings)
        payload = {"unique_code": "uc1", "chunk_index": 0}
        with patch.object(
            service, "_expand_via_adjacent_chunk_index", return_value="adjacent"
        ) as mock_adj:
            result = service._expand_single_result("idx", payload, {})
        mock_adj.assert_called_once()
        assert result == "adjacent"


# ---------------------------------------------------------------------------
# _expand_via_source_reslice
# ---------------------------------------------------------------------------


class TestExpandViaSourceReslice:
    def test_uses_file_cache_and_downloads_by_unique_code(self, mock_settings: Settings) -> None:
        sc = Mock()
        sc.download_from_bucket.return_value = b"full document text here"
        service = _make_service(mock_settings, storage_client=sc)
        payload = {
            "unique_code": "uc1",
            "file_name": "doc.txt",
            "bucket": "my-bucket",
            "start_index": 5,
            "end_index": 13,
        }
        file_cache: dict = {}
        service._expand_via_source_reslice(payload, file_cache)
        # Downloads by unique_code, not file_name
        sc.download_from_bucket.assert_called_once_with("uc1", "my-bucket")
        # After first call, cache is populated
        assert ("uc1", "my-bucket") in file_cache

    def test_file_cache_prevents_re_download(self, mock_settings: Settings) -> None:
        sc = Mock()
        sc.download_from_bucket.return_value = b"cached text"
        service = _make_service(mock_settings, storage_client=sc)
        payload = {
            "unique_code": "uc1",
            "file_name": "doc.txt",
            "bucket": None,
            "start_index": 0,
            "end_index": 6,
        }
        file_cache: dict = {("uc1", None): "pre-cached content here"}
        service._expand_via_source_reslice(payload, file_cache)
        # Not re-downloaded
        sc.download_from_bucket.assert_not_called()

    def test_window_clamped_at_zero_and_text_length(self, mock_settings: Settings) -> None:
        sc = Mock()
        sc.download_from_bucket.return_value = b"short"
        service = _make_service(mock_settings, storage_client=sc)
        payload = {
            "unique_code": "uc1",
            "file_name": "doc.txt",
            "bucket": None,
            "start_index": 0,
            "end_index": 5,
        }
        file_cache: dict = {}
        result = service._expand_via_source_reslice(payload, file_cache)
        # window extends beyond text → clamped to text boundaries
        assert result is not None
        assert len(result) <= len("short") + mock_settings.rag_adjacent_window_chars * 2

    def test_returns_none_when_file_name_missing(self, mock_settings: Settings) -> None:
        service = _make_service(mock_settings)
        payload = {"unique_code": "uc1", "start_index": 0, "end_index": 5}
        result = service._expand_via_source_reslice(payload, {})
        assert result is None

    def test_returns_none_when_unique_code_missing(self, mock_settings: Settings) -> None:
        service = _make_service(mock_settings)
        payload = {"file_name": "doc.txt", "start_index": 0, "end_index": 5}
        result = service._expand_via_source_reslice(payload, {})
        assert result is None


# ---------------------------------------------------------------------------
# _expand_via_adjacent_chunk_index
# ---------------------------------------------------------------------------


class TestExpandViaAdjacentChunkIndex:
    def test_collects_consecutive_chunks(self, mock_settings: Settings) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.list_records.return_value = [
            {
                "id": "r0",
                "payload": {
                    "unique_code": "uc1",
                    "chunk_index": 0,
                    "text": "chunk0",
                },
            },
            {
                "id": "r1",
                "payload": {
                    "unique_code": "uc1",
                    "chunk_index": 1,
                    "text": "chunk1",
                },
            },
            {
                "id": "r2",
                "payload": {
                    "unique_code": "uc1",
                    "chunk_index": 2,
                    "text": "chunk2",
                },
            },
        ]
        service = _make_service(mock_settings, vsm=vsm)
        # Starting at chunk_index=0, rag_adjacent_chunk_count determines window
        payload = {"unique_code": "uc1", "chunk_index": 0}
        result = service._expand_via_adjacent_chunk_index("idx", payload)
        assert result is not None
        # All chunks in range should be joined
        assert "chunk0" in result

    def test_no_matching_chunks_returns_none(self, mock_settings: Settings) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.list_records.return_value = []
        service = _make_service(mock_settings, vsm=vsm)
        payload = {"unique_code": "uc1", "chunk_index": 5}
        result = service._expand_via_adjacent_chunk_index("idx", payload)
        assert result is None

    def test_returns_none_when_no_unique_code(self, mock_settings: Settings) -> None:
        service = _make_service(mock_settings)
        result = service._expand_via_adjacent_chunk_index("idx", {"chunk_index": 0})
        assert result is None

    def test_returns_none_when_no_chunk_index(self, mock_settings: Settings) -> None:
        service = _make_service(mock_settings)
        result = service._expand_via_adjacent_chunk_index("idx", {"unique_code": "uc1"})
        assert result is None
