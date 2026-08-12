from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.schema import get_camel_case_config

INDEX_VECSTORE_DESCRIPTION = "Nombre del índice/colección"


class SaveDocumentVecstoreRequest(BaseModel):
    model_config = get_camel_case_config()

    file_name: str = Field(..., description="Nombre del archivo")
    base64: str | None = Field(default=None, description="Contenido del archivo en base64")
    id_document: str = Field(
        ...,
        description="ID del documento (string: en el micro Java origen es el mismo valor que unique_code, no un ID numérico separado)",
    )
    index_vecstore: str = Field(..., description=INDEX_VECSTORE_DESCRIPTION)
    unique_code: str = Field(..., description="Código único del documento")
    has_document_base64: bool = Field(True, description="Si el documento viene en base64")
    url_download_file: str | None = Field(default=None, description="URL para descargar el archivo")
    bucket: str | None = Field(default=None, description="Bucket de almacenamiento")
    list_parameters: list[dict[str, Any]] = Field(
        default_factory=list, description="Metadata adicional"
    )


class DeleteIndexVecstoreRequest(BaseModel):
    model_config = get_camel_case_config()

    index_vecstore: str = Field(..., description="Nombre del índice/colección a eliminar")


class DeleteDocumentVecstoreRequest(BaseModel):
    model_config = get_camel_case_config()

    index_vecstore: str = Field(..., description=INDEX_VECSTORE_DESCRIPTION)
    id_document: str = Field(
        ...,
        description="ID del documento a eliminar (mismo valor que unique_code en el micro Java origen)",
    )


class ListDocumentsRequest(BaseModel):
    model_config = get_camel_case_config()

    index_vecstore: str = Field(..., description=INDEX_VECSTORE_DESCRIPTION)
    limit: int = Field(default_factory=lambda: get_settings().rag_default_list_limit, ge=1, le=1000)
    metadata_filter: dict[str, Any] | None = Field(default=None, description="Filtros por metadata")


class GetEmbeddingsByUniqueCodeRequest(BaseModel):
    model_config = get_camel_case_config()

    index_vecstore: str = Field(..., description=INDEX_VECSTORE_DESCRIPTION)
    unique_code: str = Field(..., description="Código único del documento")


class SearchSimilarDocumentsRequest(BaseModel):
    model_config = get_camel_case_config()

    index_vecstore: str = Field(..., description=INDEX_VECSTORE_DESCRIPTION)
    query: str = Field(..., description="Consulta para búsqueda semántica")
    top_k: int = Field(default_factory=lambda: get_settings().rag_default_top_k, ge=1, le=100)
    metadata_filter: dict[str, Any] | None = Field(default=None, description="Filtros por metadata")


class RagQueryRequest(BaseModel):
    model_config = get_camel_case_config()

    question: str = Field(..., description="Pregunta a responder")
    top_k: int = Field(default_factory=lambda: get_settings().rag_default_top_k, ge=1, le=100)
    department: str | None = Field(default=None, description="Filtro lógico por departamento")


class EmbeddingChunkResponse(BaseModel):
    model_config = get_camel_case_config()

    chunk_id: Any
    score: float
    text: str
    chunk_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentSummaryResponse(BaseModel):
    model_config = get_camel_case_config()

    id: Any
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    text_preview: str


class SaveDocumentVecstoreResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool
    message: str
    unique_code: str
    chunks_created: int | None = None
    index_name: str


class DeleteIndexVecstoreResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool
    message: str
    index_name: str


class DeleteDocumentVecstoreResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool
    message: str
    index_name: str
    id_document: str
    deleted_count: int


class UniqueCodeDocumentResponse(BaseModel):
    """Forma liviana equivalente a ``Metadata`` en el micro Java origen."""

    model_config = get_camel_case_config()

    namespace: str
    codigo: str
    file_name: str
    id: str
    nombre_documento: str


class ListDocumentsResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool
    index_name: str
    total_results: int
    documents: list[DocumentSummaryResponse] = Field(default_factory=list)
    message: str | None = None


class GetEmbeddingsByUniqueCodeResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool
    unique_code: str
    index_name: str
    total_chunks: int
    embeddings: list[EmbeddingChunkResponse] = Field(default_factory=list)
    message: str | None = None


class SearchSimilarDocumentsResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool
    query: str
    index_name: str
    total_results: int
    results: list[DocumentSummaryResponse] = Field(default_factory=list)
    message: str | None = None


class RagQueryResponse(BaseModel):
    model_config = get_camel_case_config()

    agent: str
    question: str
    context: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    answer: str
    system_prompt: str | None = None


class OperationStatusResponse(BaseModel):
    model_config = get_camel_case_config()

    mensaje: str
    codigo: int
