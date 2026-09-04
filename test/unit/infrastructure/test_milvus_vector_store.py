"""Unit tests for MilvusVectorStore (pymilvus mocked out entirely)."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.infrastructure.vector_store.milvus_vector_store import (
    MilvusVectorStore,
    _build_filter_expression,
)


def make_settings(**kwargs: object) -> Settings:
    defaults: dict[str, object] = {
        "RAG_ENVIRONMENT": "edi-local",
        "RAG_EMBEDDING_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test",
        "VECTOR_DB_TYPE": "milvus",
        "MILVUS_HOST": "localhost",
        "MILVUS_PORT": 19530,
        "DEBUG": False,
    }
    defaults.update(kwargs)
    return Settings(**defaults)


def make_store(**kwargs: object) -> MilvusVectorStore:
    return MilvusVectorStore(make_settings(**kwargs))


# ---------------------------------------------------------------------------
# _build_filter_expression (module-level function)
# ---------------------------------------------------------------------------


class TestBuildFilterExpression:
    def test_empty_dict_returns_empty_string(self) -> None:
        assert _build_filter_expression({}) == ""

    def test_none_returns_empty_string(self) -> None:
        assert _build_filter_expression(None) == ""

    def test_single_key_produces_correct_expression(self) -> None:
        expr = _build_filter_expression({"doc_id": "abc"})
        assert expr == 'payload["doc_id"] == "abc"'

    def test_multiple_keys_joined_with_and(self) -> None:
        expr = _build_filter_expression({"env": "dev", "project": "p1"})
        # Order of dict iteration is insertion order in Python 3.7+
        assert 'payload["env"] == "dev"' in expr
        assert 'payload["project"] == "p1"' in expr
        assert " and " in expr

    def test_unsafe_key_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported filter key"):
            _build_filter_expression({"bad-key": "val"})

    def test_key_with_space_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported filter key"):
            _build_filter_expression({"bad key": "val"})

    def test_key_with_dot_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported filter key"):
            _build_filter_expression({"a.b": "val"})


# ---------------------------------------------------------------------------
# _get_client — lazy init and URI / auth
# ---------------------------------------------------------------------------


class TestMilvusGetClient:
    def test_uri_constructed_correctly(self) -> None:
        store = make_store(MILVUS_HOST="milvus-host", MILVUS_PORT=19530)
        with patch("app.infrastructure.vector_store.milvus_vector_store.MilvusClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            store._get_client()
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["uri"] == "http://milvus-host:19530"

    def test_no_auth_when_user_and_password_absent(self) -> None:
        store = make_store()
        with patch("app.infrastructure.vector_store.milvus_vector_store.MilvusClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            store._get_client()
        call_kwargs = mock_cls.call_args.kwargs
        assert "user" not in call_kwargs
        assert "password" not in call_kwargs

    def test_auth_passed_when_both_user_and_password_set(self) -> None:
        store = make_store(MILVUS_USER="admin", MILVUS_PASSWORD="secret")
        with patch("app.infrastructure.vector_store.milvus_vector_store.MilvusClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            store._get_client()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["user"] == "admin"
        assert call_kwargs["password"] == "secret"

    def test_client_is_cached_after_first_call(self) -> None:
        store = make_store()
        with patch("app.infrastructure.vector_store.milvus_vector_store.MilvusClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            c1 = store._get_client()
            c2 = store._get_client()
        assert c1 is c2
        mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# create_collection
# ---------------------------------------------------------------------------


class TestMilvusCreateCollection:
    def test_skipped_if_collection_already_exists(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        store._client = mock_client

        store.create_collection("my_col", vector_size=128)
        mock_client.create_collection.assert_not_called()

    def test_creates_schema_with_id_vector_payload_fields(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False

        # Capture the schema builder calls
        mock_schema = MagicMock()
        mock_client.create_schema.return_value = mock_schema
        mock_index_params = MagicMock()
        mock_client.prepare_index_params.return_value = mock_index_params
        store._client = mock_client

        store.create_collection("my_col", vector_size=128)

        mock_client.create_collection.assert_called_once()
        # Verify add_field was called for id, vector, payload
        field_names = [call.kwargs["field_name"] for call in mock_schema.add_field.call_args_list]
        assert "id" in field_names
        assert "vector" in field_names
        assert "payload" in field_names


# ---------------------------------------------------------------------------
# create_partition
# ---------------------------------------------------------------------------


class TestMilvusCreatePartition:
    def test_skipped_if_partition_already_exists(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.has_partition.return_value = True
        store._client = mock_client

        store.create_partition("col", "part")
        mock_client.create_partition.assert_not_called()

    def test_creates_partition_when_not_present(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.has_partition.return_value = False
        store._client = mock_client

        store.create_partition("col", "part")
        mock_client.create_partition.assert_called_once_with(
            collection_name="col", partition_name="part"
        )


# ---------------------------------------------------------------------------
# insert_vectors
# ---------------------------------------------------------------------------


class TestMilvusInsertVectors:
    def test_empty_list_returns_without_calling_insert(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        store._client = mock_client

        store.insert_vectors("col", vectors=[])
        mock_client.insert.assert_not_called()

    def test_non_empty_list_calls_insert_and_flush(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        store._client = mock_client

        store.insert_vectors("col", [[1.0, 0.0]], [{"k": "v"}], ["id-1"])
        mock_client.insert.assert_called_once()
        mock_client.flush.assert_called_once_with("col")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestMilvusSearch:
    def test_search_maps_milvus_response_correctly(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        store._client = mock_client

        # MilvusClient.search returns list[list[hit-dict]]
        mock_client.search.return_value = [
            [
                {"id": "abc", "distance": 0.95, "entity": {"payload": {"doc": "test"}}},
                {"id": "xyz", "distance": 0.80, "entity": {"payload": {"doc": "other"}}},
            ]
        ]

        results = store.search("col", [1.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0] == {"id": "abc", "score": 0.95, "payload": {"doc": "test"}}
        assert results[1] == {"id": "xyz", "score": 0.80, "payload": {"doc": "other"}}

    def test_search_empty_milvus_response(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.search.return_value = []
        store._client = mock_client

        assert store.search("col", [1.0, 0.0]) == []


# ---------------------------------------------------------------------------
# delete_collection
# ---------------------------------------------------------------------------


class TestMilvusDeleteCollection:
    def test_skipped_if_collection_does_not_exist(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        store._client = mock_client

        store.delete_collection("col")
        mock_client.drop_collection.assert_not_called()

    def test_drops_when_collection_exists(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        store._client = mock_client

        store.delete_collection("col")
        mock_client.drop_collection.assert_called_once_with("col")


# ---------------------------------------------------------------------------
# delete_records
# ---------------------------------------------------------------------------


class TestMilvusDeleteRecords:
    def test_returns_zero_if_collection_does_not_exist(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        store._client = mock_client

        count = store.delete_records("col", {"doc_id": "x"})
        assert count == 0
        mock_client.delete.assert_not_called()

    def test_returns_delete_count_from_dict_result(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_client.delete.return_value = {"delete_count": 3}
        store._client = mock_client

        count = store.delete_records("col", {"doc_id": "x"})
        assert count == 3

    def test_returns_length_of_list_result(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_client.delete.return_value = ["id1", "id2"]
        store._client = mock_client

        count = store.delete_records("col", {"doc_id": "x"})
        assert count == 2


# ---------------------------------------------------------------------------
# collection_exists
# ---------------------------------------------------------------------------


class TestMilvusCollectionExists:
    def test_delegates_to_has_collection(self) -> None:
        store = make_store()
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        store._client = mock_client

        assert store.collection_exists("col") is True
        mock_client.has_collection.assert_called_once_with("col")
