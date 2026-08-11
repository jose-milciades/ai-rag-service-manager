"""Application service for document embedding workflows.

Este service coordina el flujo de vectorizacion de documentos. No define rutas
HTTP ni implementa almacenamiento remoto directamente; usa colaboraciones de
infraestructura para descargar archivos y persistir vectores.

Su papel principal es orquestar:

- obtencion del contenido del documento
- extraccion de texto
- preparacion de metadata
- indexacion y busqueda via ``RAGService``
"""

import base64
import logging
from typing import Any

from app.core.config import Settings
from app.infrastructure.clients.storage_client import StorageClient
from app.infrastructure.embeddings.embedding_provider import EmbeddingProvider
from app.infrastructure.vector_store.vector_store_manager import VectorStoreManager
from app.services.rag.rag_service import RAGService

logger = logging.getLogger(__name__)


class DocumentEmbeddingService:
    """Service de aplicacion para indexacion y consulta documental."""

    def __init__(
        self,
        settings: Settings,
        storage_client: StorageClient,
        vector_store_manager: VectorStoreManager,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._settings = settings
        self._storage_client = storage_client
        self._vector_store_manager = vector_store_manager
        self._embedding_provider = embedding_provider
        self._rag_services: dict[str, RAGService] = {}

    def _get_rag_service(self, index_name: str) -> RAGService:
        """Obtiene o crea una instancia de ``RAGService`` por coleccion."""
        if index_name not in self._rag_services:
            self._rag_services[index_name] = RAGService(
                settings=self._settings,
                collection_name=index_name,
                vector_store_manager=self._vector_store_manager,
                embedding_provider=self._embedding_provider,
            )
        return self._rag_services[index_name]

    def save_document_to_vecstore(
        self,
        file_name: str,
        base64_content: str | None,
        id_document: str,
        index_name: str,
        unique_code: str,
        url_download_file: str | None = None,
        has_document_base64: bool = True,
        bucket: str | None = None,
        list_parameters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Carga un documento, extrae texto e indexa sus chunks en la coleccion indicada."""
        file_content = self._load_file_content(
            file_name=file_name,
            base64_content=base64_content,
            url_download_file=url_download_file,
            has_document_base64=has_document_base64,
            bucket=bucket,
        )
        text_content = self._extract_text_from_file(file_content, file_name)
        if not text_content.strip():
            raise ValueError("No text content could be extracted from the document")

        metadata = {
            "file_name": file_name,
            "id_document": id_document,
            "unique_code": unique_code,
            "bucket": bucket,
            "source": "document_upload",
        }
        metadata.update(self._normalize_parameters(list_parameters or []))

        rag_service = self._get_rag_service(index_name)
        chunks_created = rag_service.index_documents(
            documents=[text_content], metadata=[metadata], chunk=True
        )

        return {
            "success": True,
            "message": "Document indexed successfully",
            "unique_code": unique_code,
            "chunks_created": chunks_created,
            "index_name": index_name,
        }

    def delete_index(self, index_name: str) -> dict[str, Any]:
        """Elimina la coleccion vectorial completa y limpia cache local de servicios."""
        self._vector_store_manager.delete_collection(index_name)
        self._rag_services.pop(index_name, None)
        return {
            "success": True,
            "message": f"Index '{index_name}' deleted successfully",
            "index_name": index_name,
        }

    def delete_document(self, index_name: str, id_document: str) -> dict[str, Any]:
        """Elimina un unico documento (todos sus chunks) sin afectar el resto del indice."""
        rag_service = self._get_rag_service(index_name)
        deleted_count = rag_service.delete_records({"id_document": id_document})
        return {
            "success": True,
            "message": f"Document '{id_document}' deleted from index '{index_name}'",
            "index_name": index_name,
            "id_document": id_document,
            "deleted_count": deleted_count,
        }

    def list_unique_code_documents(self, namespace: str) -> list[dict[str, Any]]:
        """Lista un resumen liviano (codigo/nombre de archivo) de documentos unicos.

        Forma de salida pensada para el contrato historico que Java espera de
        ``getListUniqueCodeDocuments`` (``List<Metadata>`` con
        namespace/codigo/fileName/id/nombreDocumento) -- ver pendientes.md P-23.
        """
        rag_service = self._get_rag_service(namespace)
        records = self._vector_store_manager.list_records(
            rag_service.collection_name, limit=self._settings.rag_unique_code_list_limit
        )

        seen_codes: set[str] = set()
        documents: list[dict[str, Any]] = []
        for record in records:
            payload = record["payload"]
            code = str(payload.get("unique_code") or payload.get("id_document") or record["id"])
            if code in seen_codes:
                continue
            seen_codes.add(code)
            file_name = payload.get("file_name", "")
            documents.append(
                {
                    "namespace": namespace,
                    "codigo": code,
                    "file_name": file_name,
                    "id": str(record["id"]),
                    "nombre_documento": file_name,
                }
            )
        return documents

    def list_documents_by_index(
        self,
        index_name: str,
        limit: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Lista documentos agrupando chunks por documento logico."""
        records = self._vector_store_manager.list_records(
            index_name, limit=limit * 10, filter_conditions=metadata_filter
        )

        documents: dict[str, dict[str, Any]] = {}
        for record in records:
            payload = record["payload"]
            document_key = str(
                payload.get("unique_code") or payload.get("id_document") or record["id"]
            )
            if document_key in documents:
                continue
            documents[document_key] = {
                "id": record["id"],
                "score": None,
                "metadata": {key: value for key, value in payload.items() if key != "text"},
                "text_preview": payload.get("text", "")[:200],
            }
            if len(documents) >= limit:
                break

        return {
            "success": True,
            "index_name": index_name,
            "total_results": len(documents),
            "documents": list(documents.values()),
        }

    def get_embeddings_by_unique_code(self, index_name: str, unique_code: str) -> dict[str, Any]:
        """Recupera todos los chunks indexados para un ``unique_code``."""
        records = self._vector_store_manager.list_records(
            index_name,
            limit=self._settings.rag_max_embeddings_per_document,
            filter_conditions={"unique_code": unique_code},
        )
        records.sort(key=lambda item: item["payload"].get("chunk_index", 0))

        embeddings = [
            {
                "chunk_id": record["id"],
                "score": 1.0,
                "text": record["payload"].get("text", ""),
                "chunk_index": record["payload"].get("chunk_index", 0),
                "metadata": {
                    key: value for key, value in record["payload"].items() if key != "text"
                },
            }
            for record in records
        ]

        return {
            "success": True,
            "unique_code": unique_code,
            "index_name": index_name,
            "total_chunks": len(embeddings),
            "embeddings": embeddings,
        }

    def search_similar_documents(
        self,
        index_name: str,
        query: str,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ejecuta busqueda semantica sobre una coleccion y normaliza la respuesta."""
        results = self._get_rag_service(index_name).search(
            query=query,
            top_k=top_k,
            filter_conditions=metadata_filter,
        )
        formatted_results = [
            {
                "id": result["id"],
                "score": result["score"],
                "metadata": {
                    key: value for key, value in result["payload"].items() if key != "text"
                },
                "text_preview": result["payload"].get("text", "")[:200],
            }
            for result in results
        ]
        return {
            "success": True,
            "query": query,
            "index_name": index_name,
            "total_results": len(formatted_results),
            "results": formatted_results,
        }

    def _load_file_content(
        self,
        file_name: str,
        base64_content: str | None,
        url_download_file: str | None,
        has_document_base64: bool,
        bucket: str | None,
    ) -> bytes:
        """Resuelve el origen binario del documento desde base64, URL o bucket."""
        if has_document_base64 and base64_content:
            return base64.b64decode(base64_content)
        if url_download_file:
            return self._storage_client.download_from_url(url_download_file)
        if bucket:
            return self._storage_client.download_from_bucket(file_name, bucket)
        raise ValueError("No document source was provided")

    @staticmethod
    def _normalize_parameters(list_parameters: list[dict[str, Any]]) -> dict[str, Any]:
        """Normaliza metadata arbitraria a un unico diccionario plano.

        Acepta dos formas para cada entrada: ``{"key": ..., "value": ...}`` y
        ``{"code": ..., "value": ...}`` (esta ultima es la que manda el micro
        Java origen via ``ParametersDTO``, ver pendientes.md P-21). Sin este
        alias, entradas tipo ``{"code": "VECTOR_CHUNK_SIZE", "value": "1000"}``
        caian al fallback generico y se pisaban entre si bajo las mismas
        claves literales "code"/"value".
        """
        metadata: dict[str, Any] = {}
        for item in list_parameters:
            if "key" in item and "value" in item:
                metadata[str(item["key"])] = item["value"]
            elif "code" in item and "value" in item:
                metadata[str(item["code"])] = item["value"]
            else:
                metadata.update(item)
        return metadata

    @staticmethod
    def _extract_text_from_file(file_content: bytes, file_name: str) -> str:
        """Extrae texto de un archivo con una heuristica simple por extension."""
        extension = file_name.lower().split(".")[-1]
        if extension in {"txt", "md", "json", "csv", "py", "yaml", "yml", "html", "xml"}:
            return file_content.decode("utf-8", errors="ignore")
        if extension == "pdf":
            return file_content.decode("latin-1", errors="ignore")
        return file_content.decode("utf-8", errors="ignore")
