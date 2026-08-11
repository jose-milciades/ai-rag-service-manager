"""Vector store infrastructure adapters.

Esta capa encapsula el acceso al backend vectorial. No expone HTTP ni conoce la
logica de negocio del dominio; solo ofrece operaciones tecnicas sobre
colecciones y vectores.

El contrato estable esta definido por ``VectorStoreInterface`` y el manager
actua como facade para ocultar la implementacion concreta.
"""

import logging
import math
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from app.core.config import Settings

logger = logging.getLogger(__name__)


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
    def collection_exists(self, collection_name: str) -> bool:
        raise NotImplementedError


class InMemoryVectorStore(VectorStoreInterface):
    """Implementacion en memoria usada como adapter por defecto.

    Sirve para desarrollo local, pruebas funcionales y para mantener el servicio
    autocontenido mientras se integra un motor vectorial real.
    """

    def __init__(self) -> None:
        self._collections: dict[str, list[dict[str, Any]]] = {}

    def create_collection(self, collection_name: str, vector_size: int, **kwargs: Any) -> None:
        """Crea la coleccion si aun no existe."""
        self._collections.setdefault(collection_name, [])

    def insert_vectors(
        self,
        collection_name: str,
        vectors: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """Inserta vectores y payloads asociados en la coleccion indicada."""
        self.create_collection(collection_name, vector_size=len(vectors[0]) if vectors else 0)
        if payloads is None:
            payloads = [{} for _ in vectors]
        if ids is None:
            ids = [str(uuid4()) for _ in vectors]

        for record_id, vector, payload in zip(ids, vectors, payloads):
            self._collections[collection_name].append(
                {"id": record_id, "vector": vector, "payload": payload}
            )

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        filter_conditions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Busca por similitud coseno sobre los registros disponibles."""
        records = self.list_records(
            collection_name, limit=10_000, filter_conditions=filter_conditions
        )
        scored = []
        for record in records:
            score = self._cosine_similarity(query_vector, record["vector"])
            scored.append({"id": record["id"], "score": score, "payload": record["payload"]})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def list_records(
        self,
        collection_name: str,
        limit: int = 100,
        filter_conditions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Lista registros crudos aplicando un filtro exacto simple por payload."""
        records = list(self._collections.get(collection_name, []))
        if filter_conditions:
            records = [
                record
                for record in records
                if all(
                    record["payload"].get(key) == value for key, value in filter_conditions.items()
                )
            ]
        return records[:limit]

    def delete_collection(self, collection_name: str) -> None:
        """Elimina completamente una coleccion en memoria."""
        self._collections.pop(collection_name, None)

    def collection_exists(self, collection_name: str) -> bool:
        """Indica si la coleccion existe en el store actual."""
        return collection_name in self._collections

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        """Calcula similitud coseno entre dos vectores."""
        numerator = sum(item_left * item_right for item_left, item_right in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)


class VectorStoreManager:
    """Facade de infraestructura para el backend vectorial configurado.

    Hoy selecciona una implementacion en memoria aunque se pida ``milvus``.
    Esa decision deja estable el contrato mientras la
    integracion concreta aun no se incorpora.
    """

    def __init__(self, settings: Settings) -> None:
        requested_backend = settings.vector_db_type.lower().strip()
        self.backend_name = (
            requested_backend if requested_backend in {"memory", "milvus"} else "memory"
        )
        if self.backend_name != "memory":
            logger.warning(
                "vector backend '%s' requested but this scaffold uses the in-memory adapter until a concrete integration is added",
                self.backend_name,
            )
        self.store: VectorStoreInterface = InMemoryVectorStore()

    def create_collection(self, collection_name: str, vector_size: int, **kwargs: Any) -> None:
        """Delega la creacion de coleccion al adapter configurado."""
        self.store.create_collection(collection_name, vector_size, **kwargs)

    def insert_vectors(
        self,
        collection_name: str,
        vectors: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """Delega insercion de vectores al backend activo."""
        self.store.insert_vectors(collection_name, vectors, payloads, ids)

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        filter_conditions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Delega busqueda vectorial al backend activo."""
        return self.store.search(collection_name, query_vector, top_k, filter_conditions)

    def list_records(
        self,
        collection_name: str,
        limit: int = 100,
        filter_conditions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Delega listado de registros al backend activo."""
        return self.store.list_records(collection_name, limit, filter_conditions)

    def delete_collection(self, collection_name: str) -> None:
        """Delega borrado de coleccion al backend activo."""
        self.store.delete_collection(collection_name)

    def collection_exists(self, collection_name: str) -> bool:
        """Delega verificacion de existencia al backend activo."""
        return self.store.collection_exists(collection_name)
