"""Unit tests for InMemoryVectorStore and VectorStoreManager."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.infrastructure.vector_store.vector_store_manager import (
    InMemoryVectorStore,
    VectorStoreManager,
)


def make_settings(**kwargs: object) -> Settings:
    defaults: dict[str, object] = {
        "RAG_ENVIRONMENT": "edi-local",
        "RAG_EMBEDDING_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test",
        "VECTOR_DB_TYPE": "memory",
        "DEBUG": False,
    }
    defaults.update(kwargs)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# InMemoryVectorStore — collection lifecycle
# ---------------------------------------------------------------------------


class TestInMemoryVectorStoreCollections:
    def test_create_collection_creates_entry(self) -> None:
        store = InMemoryVectorStore()
        store.create_collection("col1", vector_size=4)
        assert "col1" in store._collections

    def test_create_collection_idempotent(self) -> None:
        store = InMemoryVectorStore()
        store.create_collection("col1", vector_size=4)
        store.insert_vectors("col1", [[1.0, 0.0, 0.0, 0.0]], [{"k": "v"}], ["id-1"])
        # Second call must not wipe the existing data
        store.create_collection("col1", vector_size=4)
        assert len(store._collections["col1"]) == 1

    def test_delete_collection_removes_collection_and_partitions(self) -> None:
        store = InMemoryVectorStore()
        store.create_collection("col1", vector_size=2)
        store.insert_vectors("col1", [[1.0, 0.0]], partition_name="p1")
        store.delete_collection("col1")
        assert "col1" not in store._collections
        assert "col1" not in store._partitions

    def test_collection_exists_true(self) -> None:
        store = InMemoryVectorStore()
        store.create_collection("col1", vector_size=2)
        assert store.collection_exists("col1") is True

    def test_collection_exists_false(self) -> None:
        store = InMemoryVectorStore()
        assert store.collection_exists("nonexistent") is False


# ---------------------------------------------------------------------------
# InMemoryVectorStore — insert_vectors
# ---------------------------------------------------------------------------


class TestInMemoryVectorStoreInsert:
    def test_insert_stores_id_vector_payload_partition(self) -> None:
        store = InMemoryVectorStore()
        store.create_collection("col", vector_size=2)
        store.insert_vectors("col", [[1.0, 0.0]], [{"doc": "a"}], ["my-id"], partition_name="p1")
        records = store._collections["col"]
        assert len(records) == 1
        rec = records[0]
        assert rec["id"] == "my-id"
        assert rec["vector"] == [1.0, 0.0]
        assert rec["payload"] == {"doc": "a"}
        assert rec["_partition"] == "p1"

    def test_insert_auto_generates_uuids_when_ids_none(self) -> None:
        store = InMemoryVectorStore()
        store.create_collection("col", vector_size=2)
        store.insert_vectors("col", [[1.0, 0.0], [0.0, 1.0]])
        ids = [r["id"] for r in store._collections["col"]]
        assert len(ids) == 2
        assert ids[0] != ids[1]
        # Must look like UUIDs (36-char with dashes)
        assert len(ids[0]) == 36

    def test_insert_uses_default_partition_when_none(self) -> None:
        store = InMemoryVectorStore()
        store.create_collection("col", vector_size=2)
        store.insert_vectors("col", [[1.0, 0.0]])
        rec = store._collections["col"][0]
        assert rec["_partition"] == InMemoryVectorStore._DEFAULT_PARTITION


# ---------------------------------------------------------------------------
# InMemoryVectorStore — search
# ---------------------------------------------------------------------------


class TestInMemoryVectorStoreSearch:
    def test_search_returns_top_k_sorted_by_similarity(self) -> None:
        store = InMemoryVectorStore()
        store.create_collection("col", vector_size=2)
        store.insert_vectors("col", [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], ids=["a", "b", "c"])
        results = store.search("col", query_vector=[1.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0]["id"] == "a"
        assert results[0]["score"] == pytest.approx(1.0)
        assert results[1]["score"] <= results[0]["score"]

    def test_search_returns_empty_list_for_empty_collection(self) -> None:
        store = InMemoryVectorStore()
        store.create_collection("col", vector_size=2)
        assert store.search("col", [1.0, 0.0]) == []

    def test_search_zero_norm_vector_returns_zero_score(self) -> None:
        store = InMemoryVectorStore()
        store.create_collection("col", vector_size=2)
        store.insert_vectors("col", [[1.0, 0.0]], ids=["a"])
        # query with zero-norm vector must not raise ZeroDivisionError
        results = store.search("col", [0.0, 0.0])
        assert results[0]["score"] == 0.0


# ---------------------------------------------------------------------------
# InMemoryVectorStore — list_records
# ---------------------------------------------------------------------------


class TestInMemoryVectorStoreListRecords:
    def setup_method(self) -> None:
        self.store = InMemoryVectorStore()
        self.store.create_collection("col", vector_size=2)
        self.store.insert_vectors(
            "col", [[1.0, 0.0]], [{"env": "dev"}], ["r1"], partition_name="p-dev"
        )
        self.store.insert_vectors(
            "col", [[0.0, 1.0]], [{"env": "prod"}], ["r2"], partition_name="p-prod"
        )

    def test_list_records_partition_filter(self) -> None:
        records = self.store.list_records("col", partition_name="p-dev")
        assert len(records) == 1
        assert records[0]["id"] == "r1"

    def test_list_records_metadata_filter(self) -> None:
        records = self.store.list_records("col", filter_conditions={"env": "prod"})
        assert len(records) == 1
        assert records[0]["id"] == "r2"

    def test_list_records_all_partitions_when_partition_name_none(self) -> None:
        records = self.store.list_records("col", partition_name=None)
        assert len(records) == 2


# ---------------------------------------------------------------------------
# InMemoryVectorStore — delete_partition / delete_records
# ---------------------------------------------------------------------------


class TestInMemoryVectorStoreDelete:
    def setup_method(self) -> None:
        self.store = InMemoryVectorStore()
        self.store.create_collection("col", vector_size=2)
        self.store.insert_vectors(
            "col", [[1.0, 0.0]], [{"env": "dev"}], ["r1"], partition_name="p-dev"
        )
        self.store.insert_vectors(
            "col", [[0.0, 1.0]], [{"env": "prod"}], ["r2"], partition_name="p-prod"
        )

    def test_delete_partition_removes_only_that_partition(self) -> None:
        self.store.delete_partition("col", "p-dev")
        remaining = self.store.list_records("col")
        ids = [r["id"] for r in remaining]
        assert "r1" not in ids
        assert "r2" in ids

    def test_delete_records_returns_count_and_applies_filter(self) -> None:
        deleted = self.store.delete_records("col", filter_conditions={"env": "dev"})
        assert deleted == 1
        remaining = self.store.list_records("col")
        assert len(remaining) == 1
        assert remaining[0]["id"] == "r2"


# ---------------------------------------------------------------------------
# VectorStoreManager
# ---------------------------------------------------------------------------


class TestVectorStoreManager:
    def test_memory_backend_for_type_memory(self) -> None:
        settings = make_settings(VECTOR_DB_TYPE="memory")
        manager = VectorStoreManager(settings=settings)
        assert isinstance(manager.store, InMemoryVectorStore)
        assert manager.backend_name == "memory"

    def test_memory_backend_for_unknown_type(self) -> None:
        settings = make_settings(VECTOR_DB_TYPE="unknown_db")
        manager = VectorStoreManager(settings=settings)
        assert isinstance(manager.store, InMemoryVectorStore)
        assert manager.backend_name == "memory"

    def test_milvus_backend_for_type_milvus(self) -> None:
        settings = make_settings(VECTOR_DB_TYPE="milvus")
        mock_milvus = MagicMock()
        with patch(
            "app.infrastructure.vector_store.vector_store_manager.MilvusVectorStore",
            return_value=mock_milvus,
        ):
            manager = VectorStoreManager(settings=settings)
        assert manager.backend_name == "milvus"
        assert manager.store is mock_milvus

    def test_delete_records_empty_filter_raises_value_error(self) -> None:
        settings = make_settings()
        manager = VectorStoreManager(settings=settings)
        with pytest.raises(ValueError, match="filter_conditions is required"):
            manager.delete_records("col", filter_conditions={})

    def test_delete_records_non_empty_filter_delegates(self) -> None:
        settings = make_settings()
        manager = VectorStoreManager(settings=settings)
        manager.store.create_collection("col", vector_size=2)
        manager.store.insert_vectors("col", [[1.0, 0.0]], [{"k": "v"}], ["id-x"])
        deleted = manager.delete_records("col", filter_conditions={"k": "v"})
        assert deleted == 1
