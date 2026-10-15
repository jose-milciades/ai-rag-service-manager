"""Esquemas de las APIs de recuperacion, ingesta de texto y extraccion.

Grupo aparte de ``schemas/embedding.py``: contrato pensado para clientes que
necesitan mas control que las rutas ``/embedding`` (p. ej. ``edi-ai-analysis-ai``)
sin alterar a los consumidores de esas rutas (backend Java, edi-ai-operator).
"""

from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.schema import get_camel_case_config

INDEX_DESCRIPTION = "Nombre del índice/colección"
FILTER_DESCRIPTION = (
    'Filtros por metadata. Igualdad: {"clave": valor}. Operadores: '
    '{"clave": {"$in": [...], "$nin": [...], "$ne": v, "$lte": n, "$gte": n, "$lt": n, "$gt": n}}'
)


class RetrievalSearchRequest(BaseModel):
    model_config = get_camel_case_config()

    index_vecstore: str = Field(..., description=INDEX_DESCRIPTION)
    query: str = Field(..., min_length=1, description="Consulta para búsqueda semántica")
    top_k: int = Field(default_factory=lambda: get_settings().rag_default_top_k, ge=1, le=100)
    metadata_filter: dict[str, Any] | None = Field(default=None, description=FILTER_DESCRIPTION)
    include_text: bool = Field(default=True, description="Devuelve el texto completo de cada chunk")
    expand_context: bool = Field(
        default=False,
        description="Añade expandedText (ventana alrededor del chunk) a cada resultado",
    )
    merge_context: bool = Field(
        default=False,
        description=(
            "Devuelve mergedContext: las ventanas de contexto de los resultados de un mismo "
            "documento, con las solapadas unidas, y los documentos separados por línea en blanco"
        ),
    )


class RetrievalResult(BaseModel):
    model_config = get_camel_case_config()

    id: Any
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None
    expanded_text: str | None = None


class RetrievalSearchResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool = True
    index_name: str
    query: str
    total_results: int
    results: list[RetrievalResult]
    merged_context: str | None = None


class RetrievalDocumentRequest(BaseModel):
    model_config = get_camel_case_config()

    index_vecstore: str = Field(..., description=INDEX_DESCRIPTION)
    unique_code: str = Field(..., description="Código único del documento (o id del documento)")
    from_chunk: int = Field(default=0, ge=0, description="Primer chunk (chunkIndex) a devolver")
    to_chunk: int | None = Field(default=None, ge=0, description="Último chunk incluido")
    max_chunks: int | None = Field(default=None, ge=1, description="Máximo de chunks a devolver")
    join_text: bool = Field(default=True, description="Incluye `text` con los chunks unidos")


class RetrievalChunk(BaseModel):
    model_config = get_camel_case_config()

    chunk_index: int
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalDocumentResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool = True
    index_name: str
    unique_code: str
    total_chunks: int
    chunks: list[RetrievalChunk]
    text: str | None = None


class IngestTextRequest(BaseModel):
    model_config = get_camel_case_config()

    index_vecstore: str = Field(..., description=INDEX_DESCRIPTION)
    id_document: str = Field(
        ...,
        min_length=1,
        description="Identificador del documento (queda también como unique_code)",
    )
    file_name: str = Field(..., min_length=1, description="Nombre lógico del documento (metadata)")
    text: str = Field(..., min_length=1, description="Texto plano a indexar")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata adicional (no pisa las claves reservadas)"
    )
    replace: bool = Field(
        default=True,
        description="Borra antes los chunks previos del mismo idDocument en este índice",
    )
    chunk_size: int | None = Field(default=None, ge=100)
    chunk_overlap: int | None = Field(default=None, ge=0)


class IngestTextResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool = True
    index_name: str
    id_document: str
    chunks_created: int
    deleted_count: int = 0
    text_stored: bool = Field(
        description="True si el texto quedó en storage (necesario para expandContext)"
    )


class ExtractTextRequest(BaseModel):
    model_config = get_camel_case_config()

    file_name: str = Field(
        ..., description="Nombre del archivo (la extensión orienta el extractor)"
    )
    base64: str | None = Field(default=None, description="Contenido del archivo en base64")
    url_download_file: str | None = Field(
        default=None, description="URL pública para descargar el archivo"
    )
    unique_code: str | None = Field(
        default=None,
        description="Código del blob en storage. Sin base64 ni URL se descarga de ahí; en PDF/imagen además activa el caché de OCR",
    )
    bucket: str | None = Field(default=None, description="Bucket de almacenamiento")


class ExtractTextResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool = True
    file_name: str
    text: str
    characters: int
