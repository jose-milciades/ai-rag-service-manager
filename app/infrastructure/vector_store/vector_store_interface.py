"""Contrato tecnico comun a cualquier backend vectorial soportado.

Separado de ``vector_store_manager.py`` para que los adapters concretos
(``InMemoryVectorStore``, ``MilvusVectorStore``) puedan importarlo sin crear
un ciclo de imports con el modulo que los selecciona (``VectorStoreManager``).
"""

from abc import ABC, abstractmethod
from typing import Any


class VectorStoreInterface(ABC):
    """Contrato tecnico para cualquier backend vectorial soportado."""

    @abstractmethod
    def create_collection(self, collection_name: str, vector_size: int, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def insert_vectors(
        self,
        collection_name: str,
        vectors: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        filter_conditions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_records(
        self,
        collection_name: str,
        limit: int = 100,
        filter_conditions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_records(
        self,
        collection_name: str,
        filter_conditions: dict[str, Any],
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def collection_exists(self, collection_name: str) -> bool:
        raise NotImplementedError
