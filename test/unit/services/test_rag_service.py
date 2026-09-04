"""Unit tests for app.services.rag.rag_service."""

from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.infrastructure.vector_store.vector_store_manager import VectorStoreManager
from app.services.rag.rag_service import RAGService, _sanitize_collection_name

# ---------------------------------------------------------------------------
# _sanitize_collection_name
# ---------------------------------------------------------------------------


class TestSanitizeCollectionName:
    def test_hyphen_replaced(self) -> None:
        assert _sanitize_collection_name("project-42") == "project_42"

    def test_space_replaced(self) -> None:
        assert _sanitize_collection_name("my project") == "my_project"

    def test_dot_replaced(self) -> None:
        assert _sanitize_collection_name("my.project") == "my_project"

    def test_unicode_replaced(self) -> None:
        # ñ is not an ASCII word char → replaced; plain 'o' is ASCII → kept
        assert _sanitize_collection_name("ñoño") == "_o_o"

    def test_empty_string_returns_underscore(self) -> None:
        assert _sanitize_collection_name("") == "_"

    def test_digit_leading_gets_prefix(self) -> None:
        assert _sanitize_collection_name("123abc") == "_123abc"

    def test_already_clean_unchanged(self) -> None:
        assert _sanitize_collection_name("valid_name_1") == "valid_name_1"

    def test_all_invalid_chars_become_underscore_prefix(self) -> None:
        # "---" → "___" which starts with "_", so no extra prefix needed
        assert _sanitize_collection_name("---") == "___"

    def test_digit_only_gets_prefix(self) -> None:
        assert _sanitize_collection_name("9") == "_9"


# ---------------------------------------------------------------------------
# RAGService.__init__
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_vsm() -> Mock:
    vsm = Mock(spec=VectorStoreManager)
    vsm.collection_exists.return_value = False
    return vsm


@pytest.fixture()
def mock_emb() -> Mock:
    emb = Mock()
    emb.dim = 1536
    emb.model_name = "text-embedding-3-small"
    return emb


def make_service(
    settings: Settings,
    vsm: Mock,
    emb: Mock,
    collection_name: str = "test_col",
) -> RAGService:
    return RAGService(
        settings=settings,
        vector_store_manager=vsm,
        embedding_provider=emb,
        collection_name=collection_name,
    )


class TestRAGServiceInit:
    def test_creates_collection_when_not_exists(
        self, mock_settings: Settings, mock_vsm: Mock, mock_emb: Mock
    ) -> None:
        mock_vsm.collection_exists.return_value = False
        make_service(mock_settings, mock_vsm, mock_emb, "my_col")
        mock_vsm.create_collection.assert_called_once_with("my_col", vector_size=1536)

    def test_skips_creation_when_collection_exists(
        self, mock_settings: Settings, mock_vsm: Mock, mock_emb: Mock
    ) -> None:
        mock_vsm.collection_exists.return_value = True
        make_service(mock_settings, mock_vsm, mock_emb, "my_col")
        mock_vsm.create_collection.assert_not_called()

    def test_always_calls_create_partition(
        self, mock_settings: Settings, mock_vsm: Mock, mock_emb: Mock
    ) -> None:
        mock_vsm.collection_exists.return_value = True
        svc = make_service(mock_settings, mock_vsm, mock_emb, "my_col")
        mock_vsm.create_partition.assert_called_once_with("my_col", svc.partition_name)

    def test_sanitizes_collection_name(
        self, mock_settings: Settings, mock_vsm: Mock, mock_emb: Mock
    ) -> None:
        mock_vsm.collection_exists.return_value = False
        svc = make_service(mock_settings, mock_vsm, mock_emb, "project-42")
        assert svc.collection_name == "project_42"

    def test_partition_name_is_sanitized_environment(
        self, mock_settings: Settings, mock_vsm: Mock, mock_emb: Mock
    ) -> None:
        # mock_settings has RAG_ENVIRONMENT="edi-local" → sanitized to "edi_local"
        svc = make_service(mock_settings, mock_vsm, mock_emb)
        assert svc.partition_name == "edi_local"


# ---------------------------------------------------------------------------
# RAGService.index_documents
# ---------------------------------------------------------------------------


class TestIndexDocuments:
    def _make_svc(self, mock_settings: Settings, mock_emb: Mock) -> RAGService:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        mock_emb.embed_documents.return_value = [[0.1] * 1536]
        return make_service(mock_settings, vsm, mock_emb)

    def test_no_chunking_single_record_indexed(
        self, mock_settings: Settings, mock_emb: Mock
    ) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        mock_emb.embed_documents.return_value = [[0.1] * 1536]
        svc = make_service(mock_settings, vsm, mock_emb)

        count = svc.index_documents(["hello world"], chunk=False)
        assert count == 1
        vsm.insert_vectors.assert_called_once()
        payloads = vsm.insert_vectors.call_args.kwargs["payloads"]
        assert payloads[0]["start_index"] == 0
        assert payloads[0]["end_index"] == len("hello world")
        assert payloads[0]["text"] == "hello world"

    def test_with_chunking_multiple_records(self, mock_settings: Settings, mock_emb: Mock) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        # chunk_size=5, overlap=0 → "hello" " worl" "d" → 3 chunks
        mock_emb.embed_documents.return_value = [[0.1] * 1536] * 3
        svc = make_service(mock_settings, vsm, mock_emb)

        count = svc.index_documents(["hello world"], chunk=True, chunk_size=5, chunk_overlap=0)
        assert count == 3

    def test_metadata_enriched_with_chunk_fields(
        self, mock_settings: Settings, mock_emb: Mock
    ) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        mock_emb.embed_documents.return_value = [[0.1] * 1536]
        svc = make_service(mock_settings, vsm, mock_emb)

        svc.index_documents(["abc"], metadata=[{"file_name": "test.txt"}], chunk=False)
        payloads = vsm.insert_vectors.call_args.kwargs["payloads"]
        p = payloads[0]
        assert p["file_name"] == "test.txt"
        assert p["chunk_index"] == 0
        assert p["start_index"] == 0
        assert p["end_index"] == 3
        assert p["text"] == "abc"

    def test_chunk_size_and_overlap_override(self, mock_settings: Settings, mock_emb: Mock) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        # text "abcde" with chunk_size=3, overlap=1 → "abc"(0,3), "cde"(2,5) → 2 chunks
        mock_emb.embed_documents.return_value = [[0.1] * 1536] * 2
        svc = make_service(mock_settings, vsm, mock_emb)

        count = svc.index_documents(["abcde"], chunk=True, chunk_size=3, chunk_overlap=1)
        assert count == 2
        payloads = vsm.insert_vectors.call_args.kwargs["payloads"]
        assert payloads[0]["chunk_index"] == 0
        assert payloads[1]["chunk_index"] == 1

    def test_returns_count_of_texts_indexed(self, mock_settings: Settings, mock_emb: Mock) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        mock_emb.embed_documents.return_value = [[0.1] * 1536] * 2
        svc = make_service(mock_settings, vsm, mock_emb)
        count = svc.index_documents(["doc one", "doc two"], chunk=False)
        assert count == 2


# ---------------------------------------------------------------------------
# RAGService._split_text
# ---------------------------------------------------------------------------


class TestSplitText:
    def _svc(self, mock_settings: Settings) -> RAGService:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        return make_service(mock_settings, vsm, emb)

    def test_normal_case_with_overlap(self, mock_settings: Settings) -> None:
        svc = self._svc(mock_settings)
        # "abcde" chunk_size=3, overlap=1 → (abc,0,3), (cde,2,5)
        chunks = svc._split_text("abcde", chunk_size=3, chunk_overlap=1)
        assert chunks == [("abc", 0, 3), ("cde", 2, 5)]

    def test_chunk_size_one(self, mock_settings: Settings) -> None:
        svc = self._svc(mock_settings)
        chunks = svc._split_text("abc", chunk_size=1, chunk_overlap=0)
        assert len(chunks) == 3
        assert chunks[0] == ("a", 0, 1)
        assert chunks[1] == ("b", 1, 2)
        assert chunks[2] == ("c", 2, 3)

    def test_chunk_size_larger_than_text(self, mock_settings: Settings) -> None:
        svc = self._svc(mock_settings)
        chunks = svc._split_text("hi", chunk_size=100, chunk_overlap=0)
        assert len(chunks) == 1
        assert chunks[0][0] == "hi"
        assert chunks[0][1] == 0
        assert chunks[0][2] == 2

    def test_overlap_clamped_to_chunk_size_minus_one(self, mock_settings: Settings) -> None:
        svc = self._svc(mock_settings)
        # chunk_size=3, overlap >= chunk_size → clamped to 2
        chunks = svc._split_text("abcde", chunk_size=3, chunk_overlap=10)
        # overlap=2: "abc"(0,3), then start=1 → "bcd"(1,4), start=2 → "cde"(2,5), start=3 → done
        assert all(len(c[0]) <= 3 for c in chunks)
        assert len(chunks) >= 2

    def test_negative_chunk_size_clamped_to_one(self, mock_settings: Settings) -> None:
        svc = self._svc(mock_settings)
        chunks = svc._split_text("ab", chunk_size=-5, chunk_overlap=0)
        # clamped to 1 → each char its own chunk
        assert len(chunks) == 2

    def test_empty_text_returns_single_empty_tuple(self, mock_settings: Settings) -> None:
        svc = self._svc(mock_settings)
        chunks = svc._split_text("", chunk_size=100, chunk_overlap=0)
        assert chunks == [("", 0, 0)]

    def test_overlap_zero_no_overlap(self, mock_settings: Settings) -> None:
        svc = self._svc(mock_settings)
        chunks = svc._split_text("abcdef", chunk_size=2, chunk_overlap=0)
        assert chunks == [("ab", 0, 2), ("cd", 2, 4), ("ef", 4, 6)]


# ---------------------------------------------------------------------------
# RAGService.search
# ---------------------------------------------------------------------------


class TestSearch:
    def _svc(self, mock_settings: Settings) -> tuple[RAGService, Mock, Mock]:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.search.return_value = [{"id": "1", "score": 0.9, "payload": {}}]
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        emb.embed_query.return_value = [0.1] * 1536
        svc = make_service(mock_settings, vsm, emb, "search_col")
        return svc, vsm, emb

    def test_calls_embed_query_and_vector_store_search(self, mock_settings: Settings) -> None:
        svc, vsm, emb = self._svc(mock_settings)
        results = svc.search("my query", top_k=3)
        emb.embed_query.assert_called_once_with("my query")
        vsm.search.assert_called_once()
        assert len(results) == 1

    def test_uses_settings_default_top_k_when_none(self, mock_settings: Settings) -> None:
        svc, vsm, _emb = self._svc(mock_settings)
        svc.search("query", top_k=None)
        call_kwargs = vsm.search.call_args.kwargs
        assert call_kwargs["top_k"] == mock_settings.rag_default_top_k

    def test_uses_given_top_k(self, mock_settings: Settings) -> None:
        svc, vsm, _emb = self._svc(mock_settings)
        svc.search("query", top_k=7)
        assert vsm.search.call_args.kwargs["top_k"] == 7

    def test_passes_partition_name(self, mock_settings: Settings) -> None:
        svc, vsm, _emb = self._svc(mock_settings)
        svc.search("query")
        assert vsm.search.call_args.kwargs["partition_name"] == svc.partition_name

    def test_passes_filter_conditions(self, mock_settings: Settings) -> None:
        svc, vsm, _emb = self._svc(mock_settings)
        svc.search("query", filter_conditions={"id_document": "doc1"})
        assert vsm.search.call_args.kwargs["filter_conditions"] == {"id_document": "doc1"}


# ---------------------------------------------------------------------------
# RAGService.clear_collection
# ---------------------------------------------------------------------------


class TestClearCollection:
    def test_calls_delete_partition(self, mock_settings: Settings) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        svc = make_service(mock_settings, vsm, emb, "my_col")

        svc.clear_collection()
        vsm.delete_partition.assert_called_once_with(svc.collection_name, svc.partition_name)


# ---------------------------------------------------------------------------
# RAGService.delete_records
# ---------------------------------------------------------------------------


class TestDeleteRecords:
    def test_delegates_to_vector_store_with_partition(self, mock_settings: Settings) -> None:
        vsm = Mock(spec=VectorStoreManager)
        vsm.collection_exists.return_value = True
        vsm.delete_records.return_value = 3
        emb = Mock()
        emb.dim = 1536
        emb.model_name = "text-embedding-3-small"
        svc = make_service(mock_settings, vsm, emb, "my_col")

        result = svc.delete_records({"id_document": "doc1"})
        assert result == 3
        vsm.delete_records.assert_called_once_with(
            svc.collection_name,
            {"id_document": "doc1"},
            partition_name=svc.partition_name,
        )
