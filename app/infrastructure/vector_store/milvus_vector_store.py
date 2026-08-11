"""Milvus adapter for VectorStoreInterface.

Cada registro se guarda con tres campos: ``id`` (primary key string),
``vector`` (float vector, dimension segun el modelo de embeddings activo) y
``payload`` (JSON) — este ultimo preserva el contrato de dict libre que ya
usa el resto de la aplicacion (``record["payload"].get(...)``) sin tener que
declarar una columna Milvus por cada clave de metadata posible.
"""

import json
import logging
import re
from typing import Any
from uuid import uuid4

from pymilvus import DataType, MilvusClient

from app.core.config import Settings
from app.infrastructure.vector_store.vector_store_interface import VectorStoreInterface

logger = logging.getLogger(__name__)

_PAYLOAD_FIELD = "payload"
_VECTOR_FIELD = "vector"
_ID_FIELD = "id"
_ID_MAX_LENGTH = 64

# Los nombres de clave en filter_conditions se interpolan directo en la
# expresion de filtro de Milvus (``payload["<key>"] == ...``). Sin esta
# validacion, una clave con comillas/operadores podria escapar la expresion
# esperada (inyeccion de filtro) — igual que se valida la URL en
# storage_client.py para evitar SSRF, aqui se valida la forma de la clave.
_SAFE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def _build_filter_expression(filter_conditions: dict[str, Any] | None) -> str:
    if not filter_conditions:
        return ""

    clauses = []
    for key, value in filter_conditions.items():
        if not _SAFE_KEY_PATTERN.match(key):
            raise ValueError(f"Unsupported filter key: {key!r}")
        clauses.append(f'{_PAYLOAD_FIELD}["{key}"] == {json.dumps(value)}')
    return " and ".join(clauses)


class MilvusVectorStore(VectorStoreInterface):
    """Adapter tecnico que habla con un Milvus real via ``MilvusClient``."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: MilvusClient | None = None

    def _get_client(self) -> MilvusClient:
        if self._client is not None:
            return self._client

        uri = f"http://{self._settings.milvus_host}:{self._settings.milvus_port}"
        client_kwargs: dict[str, Any] = {"uri": uri}
        if self._settings.milvus_db_name:
            client_kwargs["db_name"] = self._settings.milvus_db_name
        if self._settings.milvus_user and self._settings.milvus_password:
            client_kwargs["user"] = self._settings.milvus_user
            client_kwargs["password"] = self._settings.milvus_password

        logger.info("connecting to milvus at %s", uri)
        self._client = MilvusClient(**client_kwargs)
        return self._client

    def create_collection(self, collection_name: str, vector_size: int, **kwargs: Any) -> None:
        """Crea la coleccion (id + vector + payload JSON) si aun no existe."""
        client = self._get_client()
        if client.has_collection(collection_name):
            return

        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(
            field_name=_ID_FIELD,
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=_ID_MAX_LENGTH,
        )
        schema.add_field(field_name=_VECTOR_FIELD, datatype=DataType.FLOAT_VECTOR, dim=vector_size)
        schema.add_field(field_name=_PAYLOAD_FIELD, datatype=DataType.JSON)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name=_VECTOR_FIELD,
            index_type=self._settings.milvus_index_type,
            metric_type=self._settings.milvus_metric_type,
            params={"nlist": self._settings.milvus_index_nlist},
        )

        logger.info("creating milvus collection %s (dim=%s)", collection_name, vector_size)
        client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
        )

    def insert_vectors(
        self,
        collection_name: str,
        vectors: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """Inserta vectores y payloads; hace flush para que sean buscables de inmediato."""
        if not vectors:
            return
        if payloads is None:
            payloads = [{} for _ in vectors]
        if ids is None:
            ids = [str(uuid4()) for _ in vectors]

        client = self._get_client()
        data = [
            {_ID_FIELD: record_id, _VECTOR_FIELD: vector, _PAYLOAD_FIELD: payload}
            for record_id, vector, payload in zip(ids, vectors, payloads)
        ]
        client.insert(collection_name=collection_name, data=data)
        client.flush(collection_name)

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        filter_conditions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Busqueda por similitud vectorial nativa de Milvus."""
        client = self._get_client()
        results = client.search(
            collection_name=collection_name,
            data=[query_vector],
            anns_field=_VECTOR_FIELD,
            search_params={
                "metric_type": self._settings.milvus_metric_type,
                "params": {"nprobe": self._settings.milvus_search_nprobe},
            },
            limit=top_k,
            filter=_build_filter_expression(filter_conditions),
            output_fields=[_PAYLOAD_FIELD],
        )
        hits = results[0] if results else []
        return [
            {
                "id": hit["id"],
                "score": hit["distance"],
                "payload": hit["entity"].get(_PAYLOAD_FIELD, {}),
            }
            for hit in hits
        ]

    def list_records(
        self,
        collection_name: str,
        limit: int = 100,
        filter_conditions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Lista registros crudos via query() (sin busqueda vectorial)."""
        client = self._get_client()
        rows = client.query(
            collection_name=collection_name,
            filter=_build_filter_expression(filter_conditions),
            output_fields=[_ID_FIELD, _VECTOR_FIELD, _PAYLOAD_FIELD],
            limit=limit,
        )
        return [
            {
                "id": row[_ID_FIELD],
                "vector": row[_VECTOR_FIELD],
                "payload": row.get(_PAYLOAD_FIELD, {}),
            }
            for row in rows
        ]

    def delete_collection(self, collection_name: str) -> None:
        """Elimina la coleccion si existe."""
        client = self._get_client()
        if client.has_collection(collection_name):
            client.drop_collection(collection_name)

    def delete_records(self, collection_name: str, filter_conditions: dict[str, Any]) -> int:
        """Elimina registros que cumplan el filtro indicado; retorna cuantos se borraron."""
        client = self._get_client()
        if not client.has_collection(collection_name):
            return 0
        result = client.delete(
            collection_name=collection_name,
            filter=_build_filter_expression(filter_conditions),
        )
        # Igual que en insert_vectors: sin flush, el borrado no es visible de
        # inmediato para queries subsiguientes (ver comentario de insert_vectors).
        client.flush(collection_name)
        if isinstance(result, dict):
            return int(result.get("delete_count", 0))
        if isinstance(result, list):
            return len(result)
        return 0

    def collection_exists(self, collection_name: str) -> bool:
        return self._get_client().has_collection(collection_name)
