"""Filtros de metadata: igualdad (contrato original) y operadores $."""

from typing import ClassVar

import pytest

from app.infrastructure.vector_store.filters import (
    build_milvus_expression,
    is_operator_filter,
    matches,
)


class TestMilvusExpression:
    def test_equality_is_unchanged(self) -> None:
        expr = build_milvus_expression({"unique_code": "abc", "n": 3})
        assert expr == 'payload["unique_code"] == "abc" and payload["n"] == 3'

    def test_empty_filter(self) -> None:
        assert build_milvus_expression(None) == ""
        assert build_milvus_expression({}) == ""

    def test_in_and_nin(self) -> None:
        assert build_milvus_expression({"f": {"$in": ["a", "b"]}}) == 'payload["f"] in ["a", "b"]'
        assert build_milvus_expression({"f": {"$nin": ["a"]}}) == (
            '(not exists payload["f"] or payload["f"] not in ["a"])'
        )

    def test_range_operators(self) -> None:
        expr = build_milvus_expression({"chunk_index": {"$gte": 2, "$lte": 10}})
        assert expr == 'payload["chunk_index"] >= 2 and payload["chunk_index"] <= 10'

    def test_unknown_operator_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_milvus_expression({"f": {"$regex": "x"}})

    def test_bad_key_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_milvus_expression({'a"] or 1==1 or payload["b': 1})

    def test_in_requires_list_and_range_requires_number(self) -> None:
        with pytest.raises(ValueError):
            build_milvus_expression({"f": {"$in": "a"}})
        with pytest.raises(ValueError):
            build_milvus_expression({"f": {"$lte": "5"}})

    def test_values_are_escaped(self) -> None:
        expr = build_milvus_expression({"f": {"$in": ['a" or 1==1 or "']}})
        assert '\\"' in expr


class TestMatches:
    payload: ClassVar[dict[str, object]] = {
        "file_name": "a.pdf",
        "chunk_index": 3,
        "unique_code": "x",
    }

    def test_equality(self) -> None:
        assert matches(self.payload, {"file_name": "a.pdf"})
        assert not matches(self.payload, {"file_name": "b.pdf"})

    def test_nin_includes_missing_key(self) -> None:
        assert matches(self.payload, {"file_name": {"$nin": ["b.pdf"]}})
        assert not matches(self.payload, {"file_name": {"$nin": ["a.pdf"]}})
        assert matches(self.payload, {"other": {"$nin": ["z"]}})

    def test_in_and_ne(self) -> None:
        assert matches(self.payload, {"file_name": {"$in": ["a.pdf", "c"]}})
        assert not matches(self.payload, {"file_name": {"$ne": "a.pdf"}})

    def test_ranges(self) -> None:
        assert matches(self.payload, {"chunk_index": {"$gte": 3, "$lte": 3}})
        assert not matches(self.payload, {"chunk_index": {"$gt": 3}})
        assert not matches({}, {"chunk_index": {"$lte": 10}})

    def test_dict_without_operators_is_equality(self) -> None:
        assert not is_operator_filter({"a": 1})
        assert matches({"meta": {"a": 1}}, {"meta": {"a": 1}})
