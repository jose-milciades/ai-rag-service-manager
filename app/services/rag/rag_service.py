"""Core RAG retrieval service.

Este modulo contiene la logica central de indexacion y recuperacion semantica.
No conoce HTTP y no depende de controllers. Trabaja sobre una abstraccion de
vector store para que la infraestructura pueda cambiar sin romper el contrato.

El embedding real (modelo cargado una sola vez) vive en ``EmbeddingProvider``
y se inyecta aqui; ``RAGService`` no sabe que libreria concreta lo genera.
"""

import re
from typing import Any

from app.core.config import Settings
from app.infrastructure.embeddings.embedding_provider import EmbeddingProvider
from app.infrastructure.vector_store.vector_store_manager import VectorStoreManager

# re.ASCII: sin este flag, \W tambien dejaria pasar letras unicode (acentos,
# otros alfabetos) por ser "word chars" en Python -- Milvus exige ASCII puro.
_INVALID_COLLECTION_CHARS = re.compile(r"\W", re.ASCII)


def _sanitize_collection_name(name: str) -> str:
    """Milvus solo acepta letras, numeros y guion bajo en nombres de coleccion
    (ver pendientes.md P-25 -- encontrado probando P-10 contra Milvus real:
    ``project-42`` es un nombre valido en el backend en memoria pero invalido
    en Milvus). Cualquier otro caracter (guiones, espacios, puntos, etc.) se
    reemplaza por "_"; si el resultado queda vacio o empieza con un digito
    (tambien invalido en Milvus), se le antepone un guion bajo.
    """
    sanitized = _INVALID_COLLECTION_CHARS.sub("_", name)
    if not sanitized:
        return "_"
    if sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    return sanitized


class RAGService:
    """Servicio central para chunking, embedding, indexacion y retrieval.

    Coleccion Milvus = proyecto solo, sin concatenar (ej. ``project_127``).
    Particion Milvus = ambiente (``Settings.rag_environment``, ej.
    ``edi_dev``) dentro de esa coleccion -- ver pendientes.md P-33. Asi
    varios ambientes (edi-local/edi-dev/edi-stage/edi-prod) que comparten la
    misma instancia Milvus pueden convivir en la misma coleccion por
    proyecto sin mezclar sus datos, y son administrables por separado
    (browsear/borrar un ambiente puntual sin tocar los demas) en vez de
    quedar todo concatenado en un unico nombre de coleccion.
    """

    def __init__(
        self,
        settings: Settings,
        vector_store_manager: VectorStoreManager,
        embedding_provider: EmbeddingProvider,
        collection_name: str,
    ) -> None:
        self._settings = settings
        self._vector_store = vector_store_manager
        self._embedding_provider = embedding_provider
        self.collection_name = _sanitize_collection_name(collection_name)
        self.partition_name = _sanitize_collection_name(settings.rag_environment)
        self.embedding_model = embedding_provider.model_name
        self._vector_size = embedding_provider.dim
        if not self._vector_store.collection_exists(self.collection_name):
            self._vector_store.create_collection(
                self.collection_name, vector_size=self._vector_size
            )
        self._vector_store.create_partition(self.collection_name, self.partition_name)

    def index_documents(
        self,
        documents: list[str],
        metadata: list[dict[str, Any]] | None = None,
        chunk: bool = True,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> int:
        """Indexa documentos completos o sus chunks en la coleccion activa.

        ``chunk_size``/``chunk_overlap`` opcionales permiten un override por
        request (ver pendientes.md P-35): sin ellos, cae al default global de
        ``Settings``, igual que antes.
        """
        metadata = metadata or [{} for _ in documents]
        texts_to_index: list[str] = []
        metadata_to_index: list[dict[str, Any]] = []

        for document, meta in zip(documents, metadata):
            # start_index/end_index (offset de caracteres en el texto
            # original) se persisten para poder reconstruir despues una
            # ventana de contexto exacta alrededor de un chunk (ver
            # pendientes.md P-37, "adjacent chunks"). Documentos indexados
            # antes de este cambio no tendran estas dos claves -- se
            # distingue por su ausencia, no se retro-completan.
            chunks = (
                self._split_text(document, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                if chunk
                else [(document, 0, len(document))]
            )
            for chunk_index, (current_chunk, start_index, end_index) in enumerate(chunks):
                texts_to_index.append(current_chunk)
                metadata_to_index.append(
                    {
                        **meta,
                        "chunk_index": chunk_index,
                        "start_index": start_index,
                        "end_index": end_index,
                        "text": current_chunk,
                    }
                )

        vectors = self._embedding_provider.embed_documents(texts_to_index)
        self._vector_store.insert_vectors(
            self.collection_name,
            vectors=vectors,
            payloads=metadata_to_index,
            partition_name=self.partition_name,
        )
        return len(texts_to_index)

    def search(
        self,
        query: str,
        top_k: int | None = None,
        filter_conditions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Busca chunks similares a una consulta dentro de la particion (ambiente) activa."""
        effective_top_k = top_k or self._settings.rag_default_top_k
        return self._vector_store.search(
            collection_name=self.collection_name,
            query_vector=self._embedding_provider.embed_query(query),
            top_k=effective_top_k,
            filter_conditions=filter_conditions,
            partition_name=self.partition_name,
        )

    def clear_collection(self) -> None:
        """Elimina solo la particion (ambiente) activa, sin afectar otros
        ambientes que compartan la misma coleccion/proyecto (ver
        pendientes.md P-33)."""
        self._vector_store.delete_partition(self.collection_name, self.partition_name)

    def delete_records(self, filter_conditions: dict[str, Any]) -> int:
        """Elimina registros de la particion (ambiente) activa que cumplan el filtro indicado."""
        return self._vector_store.delete_records(
            self.collection_name, filter_conditions, partition_name=self.partition_name
        )

    def _split_text(
        self,
        text: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> list[tuple[str, int, int]]:
        """Divide un texto en chunks usando tamano y overlap configurados.

        ``chunk_size``/``chunk_overlap`` explicitos (por request) tienen
        prioridad sobre el default global de ``Settings`` si vienen. Se
        clampan a valores no negativos: un valor invalido/negativo mandado
        por request no debe producir un comportamiento distinto a omitirlo.

        Devuelve ``(chunk_text, start_index, end_index)`` por chunk --
        ``start_index``/``end_index`` son offsets de caracteres sobre
        ``text``, usados para "adjacent chunks" (ver pendientes.md P-37).
        """
        raw_chunk_size = chunk_size if chunk_size is not None else self._settings.rag_chunk_size
        effective_chunk_size = max(raw_chunk_size, 1)
        raw_overlap = chunk_overlap if chunk_overlap is not None else self._settings.rag_chunk_overlap
        overlap = (
            max(0, min(raw_overlap, effective_chunk_size - 1)) if effective_chunk_size > 1 else 0
        )
        chunks: list[tuple[str, int, int]] = []
        start = 0
        while start < len(text):
            end = start + effective_chunk_size
            actual_end = min(end, len(text))
            chunks.append((text[start:end], start, actual_end))
            if end >= len(text):
                break
            start = end - overlap
        return chunks or [(text, 0, len(text))]
