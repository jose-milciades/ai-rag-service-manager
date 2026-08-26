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
import io
import logging
from typing import Any

import pdfplumber

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

        normalized_parameters = self._normalize_parameters(list_parameters or [])
        metadata = {
            "file_name": file_name,
            "id_document": id_document,
            "unique_code": unique_code,
            "bucket": bucket,
            "source": "document_upload",
        }
        metadata.update(normalized_parameters)

        # VECTOR_CHUNK_SIZE/VECTOR_CHUNK_OVERLAP: parametros configurables por
        # admin del lado de Java (tabla Parameters), reenviados aqui via
        # list_parameters -- ver pendientes.md P-35. Antes solo quedaban
        # guardados como metadata inerte; ahora tambien controlan el chunking
        # real de este documento puntual, con fallback al default global de
        # Settings si no vienen o no son un entero valido.
        chunk_size = self._parse_int_parameter(normalized_parameters, "VECTOR_CHUNK_SIZE")
        chunk_overlap = self._parse_int_parameter(normalized_parameters, "VECTOR_CHUNK_OVERLAP")

        rag_service = self._get_rag_service(index_name)
        chunks_created = rag_service.index_documents(
            documents=[text_content],
            metadata=[metadata],
            chunk=True,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        return {
            "success": True,
            "message": "Document indexed successfully",
            "unique_code": unique_code,
            "chunks_created": chunks_created,
            "index_name": index_name,
        }

    def delete_index(self, index_name: str) -> dict[str, Any]:
        """Elimina los datos de este proyecto para el ambiente actual (particion,
        ver pendientes.md P-33) y limpia cache local de servicios. No afecta
        otros ambientes que compartan la misma coleccion/proyecto."""
        rag_service = self._get_rag_service(index_name)
        rag_service.clear_collection()
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
            rag_service.collection_name,
            limit=self._settings.rag_unique_code_list_limit,
            partition_name=rag_service.partition_name,
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
        rag_service = self._get_rag_service(index_name)
        records = self._vector_store_manager.list_records(
            rag_service.collection_name,
            limit=limit * 10,
            filter_conditions=metadata_filter,
            partition_name=rag_service.partition_name,
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
        rag_service = self._get_rag_service(index_name)
        records = self._vector_store_manager.list_records(
            rag_service.collection_name,
            limit=self._settings.rag_max_embeddings_per_document,
            filter_conditions={"unique_code": unique_code},
            partition_name=rag_service.partition_name,
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
        expand_context: bool = False,
    ) -> dict[str, Any]:
        """Ejecuta busqueda semantica sobre una coleccion y normaliza la respuesta.

        ``expand_context`` (opcional, default ``False``): "adjacent chunks"
        -- ver pendientes.md P-37. Sin el flag, comportamiento identico al de
        siempre. Con el flag, cada resultado incorpora ``expanded_text`` con
        una ventana de contexto ampliada alrededor del chunk que matcheo
        (``text_preview`` no cambia, sigue truncado a 200 caracteres, para no
        alterar el contrato existente de nadie que no pida expansion).
        """
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
        if expand_context:
            self._expand_context(index_name, results, formatted_results)
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
        return self._storage_client.download_from_bucket(file_name, bucket)

    def _expand_context(
        self,
        index_name: str,
        raw_results: list[dict[str, Any]],
        formatted_results: list[dict[str, Any]],
    ) -> None:
        """Rellena ``expanded_text`` en cada resultado (ver pendientes.md P-37).

        Falla de forma aislada por resultado: un error expandiendo uno (ej.
        el archivo original ya no existe en storage) no debe tumbar la
        busqueda completa ni afectar a los demas resultados -- se loguea y
        ese resultado en particular simplemente no trae ``expanded_text``.
        """
        file_cache: dict[tuple[str, str | None], str] = {}
        for raw, formatted in zip(raw_results, formatted_results):
            try:
                expanded = self._expand_single_result(index_name, raw["payload"], file_cache)
                if expanded:
                    formatted["expanded_text"] = expanded
            except Exception:
                logger.exception(
                    "fallo expandiendo contexto para resultado id=%s en %s",
                    raw.get("id"),
                    index_name,
                )

    def _expand_single_result(
        self,
        index_name: str,
        payload: dict[str, Any],
        file_cache: dict[tuple[str, str | None], str],
    ) -> str | None:
        """Elige la estrategia de expansion segun la metadata disponible.

        Chunks indexados con ``start_index``/``end_index`` (desde este
        cambio en adelante) usan la ventana exacta por offset de caracteres
        sobre el documento original. Chunks mas viejos, sin esa metadata,
        caen al fallback por rango de ``chunk_index`` -- mismo criterio dual
        que ya resuelve `edi-ai-analysis-ai` para el mismo problema.
        """
        if payload.get("start_index") is not None and payload.get("end_index") is not None:
            return self._expand_via_source_reslice(payload, file_cache)
        return self._expand_via_adjacent_chunk_index(index_name, payload)

    def _expand_via_source_reslice(
        self,
        payload: dict[str, Any],
        file_cache: dict[tuple[str, str | None], str],
    ) -> str | None:
        """Re-descarga el documento original y recorta una ventana exacta.

        A diferencia de `edi-ai-analysis-ai` (que necesitaba guardar una
        copia de texto plano aparte solo para esto), storage y extraccion de
        texto ya viven en este mismo servicio -- se reusa el archivo
        original tal cual se subio. ``file_cache`` evita re-descargar el
        mismo archivo si varios resultados del mismo documento matchearon en
        una sola busqueda.
        """
        file_name = payload.get("file_name")
        if not file_name:
            return None
        bucket = payload.get("bucket")
        cache_key = (str(file_name), str(bucket) if bucket else None)
        if cache_key not in file_cache:
            file_content = self._storage_client.download_from_bucket(file_name, bucket)
            file_cache[cache_key] = self._extract_text_from_file(file_content, file_name)
        full_text = file_cache[cache_key]

        start_index = int(payload["start_index"])
        end_index = int(payload["end_index"])
        window = self._settings.rag_adjacent_window_chars
        window_start = max(0, start_index - window)
        window_end = min(len(full_text), end_index + window)
        return full_text[window_start:window_end]

    def _expand_via_adjacent_chunk_index(
        self,
        index_name: str,
        payload: dict[str, Any],
    ) -> str | None:
        """Fallback para chunks sin ``start_index``: trae los siguientes N
        chunks consecutivos (mismo ``unique_code``, ``chunk_index`` mayor)
        via ``list_records`` y los concatena en orden.

        Usa un filtro simple por igualdad (``unique_code``) y descarta el
        resto en Python en vez de armar un filtro de rango en Milvus -- mas
        barato que una segunda busqueda vectorial, y no requiere extender el
        motor de filtros (``_build_filter_expression`` solo soporta
        igualdad hoy).
        """
        unique_code = payload.get("unique_code")
        chunk_index = payload.get("chunk_index")
        if unique_code is None or chunk_index is None:
            return None
        rag_service = self._get_rag_service(index_name)
        records = self._vector_store_manager.list_records(
            rag_service.collection_name,
            limit=self._settings.rag_max_embeddings_per_document,
            filter_conditions={"unique_code": unique_code},
            partition_name=rag_service.partition_name,
        )
        chunk_count = self._settings.rag_adjacent_chunk_count
        target_range = range(int(chunk_index), int(chunk_index) + chunk_count + 1)
        adjacent = [
            record
            for record in records
            if record["payload"].get("chunk_index") in target_range
        ]
        if not adjacent:
            return None
        adjacent.sort(key=lambda record: record["payload"].get("chunk_index", 0))
        return "\n".join(record["payload"].get("text", "") for record in adjacent)

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
    def _parse_int_parameter(parameters: dict[str, Any], key: str) -> int | None:
        """Convierte un valor de ``list_parameters`` (siempre string, ver P-21) a int.

        Devuelve ``None`` si la clave no vino o no es un entero valido -- en
        ese caso ``RAGService`` cae al default global (``rag_chunk_size``/
        ``rag_chunk_overlap``), igual que si Java nunca hubiera mandado el
        parametro. Un valor malformado no debe tumbar la indexacion completa.
        """
        value = parameters.get(key)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning("parametro %s con valor no entero, se ignora: %r", key, value)
            return None

    @staticmethod
    def _extract_text_from_file(file_content: bytes, file_name: str) -> str:
        """Extrae texto de un archivo con una heuristica simple por extension."""
        extension = file_name.lower().split(".")[-1]
        if extension in {"txt", "md", "json", "csv", "py", "yaml", "yml", "html", "xml"}:
            return file_content.decode("utf-8", errors="ignore")
        if extension == "pdf":
            return DocumentEmbeddingService._extract_text_from_pdf(file_content)
        return file_content.decode("utf-8", errors="ignore")

    @staticmethod
    def _extract_text_from_pdf(file_content: bytes) -> str:
        """Extrae el texto real de un PDF con contenido de texto (no escaneado).

        Antes de esto, un PDF se trataba con
        ``file_content.decode("latin-1", errors="ignore")`` -- decodificaba
        los bytes crudos del archivo (streams comprimidos con FlateDecode,
        tabla xref, anotaciones) como si fueran texto plano, en vez de
        extraer el contenido real de las paginas. Confirmado real con una
        prueba end-to-end (ver pendientes.md P-39): el texto indexado eran
        objetos PDF binarios, no los parrafos del documento.

        Usa `pdfplumber`, la misma libreria que usa `edi-ai-analysis-ai`
        (`ReadTextBase64._read_text_pdf_without_images`) para el caso de
        PDFs con texto real -- se mantiene el mismo separador de pagina
        (``*page-break*``) por consistencia con ese formato ya conocido por
        el resto del sistema. **No** se replica el resto de ese pipeline
        (deteccion de PDF-solo-imagenes + OCR via Google Vision para
        escaneados, ni DOC/PPT/XLS via Spire) -- fuera de alcance de este
        fix puntual; un PDF escaneado (sin texto real en sus paginas) hoy
        simplemente produce paginas vacias, no un error.
        """
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n*page-break*\n".join(pages)
