"""HTTP controller for document embedding and RAG query operations.

Este archivo pertenece a la capa de API. Su rol es exponer endpoints HTTP para
indexacion, consulta y recuperacion de contexto RAG.

No implementa logica de negocio compleja. Todo el trabajo real se delega a:

- ``DocumentEmbeddingService`` para indexacion y busqueda documental
- ``RAGAgent`` para construir respuestas basadas en contexto recuperado
"""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.dependencies.services import get_document_embedding_service, get_rag_agent
from app.schemas.embedding import (
    DeleteIndexVecstoreRequest,
    GetEmbeddingsByUniqueCodeRequest,
    GetEmbeddingsByUniqueCodeResponse,
    ListDocumentsRequest,
    ListDocumentsResponse,
    OperationStatusResponse,
    RagQueryRequest,
    RagQueryResponse,
    SaveDocumentVecstoreRequest,
    SaveDocumentVecstoreResponse,
    SearchSimilarDocumentsRequest,
    SearchSimilarDocumentsResponse,
)
from app.services.embedding.document_embedding_service import DocumentEmbeddingService
from app.services.rag.rag_agent import RAGAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embedding", tags=["embedding"])

# Dependencias compartidas de FastAPI para mantener handlers mas legibles.
EmbeddingServiceDep = Annotated[
    DocumentEmbeddingService,
    Depends(get_document_embedding_service),
]
RagAgentDep = Annotated[RAGAgent, Depends(get_rag_agent)]


@router.post(
    "/save_document_vecstore",
    status_code=status.HTTP_200_OK,
    summary="Save document to vector store",
)
async def save_document_vecstore(
    request: SaveDocumentVecstoreRequest,
    service: EmbeddingServiceDep,
) -> SaveDocumentVecstoreResponse:
    """Indexa un documento en una coleccion vectorial.

    El controller recibe el request, delega al service la extraccion y la
    indexacion, y convierte el resultado a un response schema.
    """
    try:
        result = service.save_document_to_vecstore(
            file_name=request.file_name,
            base64_content=request.base64,
            id_document=request.id_document,
            index_name=request.index_vecstore,
            unique_code=request.unique_code,
            url_download_file=request.url_download_file,
            has_document_base64=request.has_document_base64,
            bucket=request.bucket,
            list_parameters=request.list_parameters,
        )
        return SaveDocumentVecstoreResponse(**result)
    except Exception as exc:
        logger.exception("error saving document to vecstore", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving document: {exc}",
        ) from exc


@router.post(
    "/delete_index_vecstore",
    status_code=status.HTTP_200_OK,
    summary="Delete vector store index",
)
async def delete_index_vecstore(
    request: DeleteIndexVecstoreRequest,
    background_tasks: BackgroundTasks,
    service: EmbeddingServiceDep,
) -> OperationStatusResponse:
    """Solicita el borrado asincrono de una coleccion vectorial.

    La operacion se agenda como background task porque conceptualmente puede ser
    costosa en un backend vectorial real.
    """
    try:
        background_tasks.add_task(service.delete_index, request.index_vecstore)
        return OperationStatusResponse(
            mensaje=f"Index deletion started: {request.index_vecstore}",
            codigo=200,
        )
    except Exception as exc:
        logger.exception("error deleting index", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting index: {exc}",
        ) from exc


@router.post(
    "/list_documents",
    status_code=status.HTTP_200_OK,
    summary="List documents in index",
)
async def list_documents(
    request: ListDocumentsRequest,
    service: EmbeddingServiceDep,
) -> ListDocumentsResponse:
    """Lista documentos de una coleccion con filtros opcionales."""
    try:
        result = service.list_documents_by_index(
            index_name=request.index_vecstore,
            limit=request.limit,
            metadata_filter=request.metadata_filter,
        )
        return ListDocumentsResponse(**result)
    except Exception as exc:
        logger.exception("error listing documents", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing documents: {exc}",
        ) from exc


@router.post(
    "/get_embeddings_by_unique_code",
    status_code=status.HTTP_200_OK,
    summary="Get all embeddings for a document",
)
async def get_embeddings_by_unique_code(
    request: GetEmbeddingsByUniqueCodeRequest,
    service: EmbeddingServiceDep,
) -> GetEmbeddingsByUniqueCodeResponse:
    """Obtiene los chunks indexados para un documento identificado por unique code."""
    try:
        result = service.get_embeddings_by_unique_code(
            index_name=request.index_vecstore,
            unique_code=request.unique_code,
        )
        return GetEmbeddingsByUniqueCodeResponse(**result)
    except Exception as exc:
        logger.exception("error getting embeddings", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting embeddings: {exc}",
        ) from exc


@router.post(
    "/search_similar_documents",
    status_code=status.HTTP_200_OK,
    summary="Search similar documents",
)
async def search_similar_documents(
    request: SearchSimilarDocumentsRequest,
    service: EmbeddingServiceDep,
) -> SearchSimilarDocumentsResponse:
    """Ejecuta una consulta semantica contra la coleccion indicada."""
    try:
        result = service.search_similar_documents(
            index_name=request.index_vecstore,
            query=request.query,
            top_k=request.top_k,
            metadata_filter=request.metadata_filter,
        )
        return SearchSimilarDocumentsResponse(**result)
    except Exception as exc:
        logger.exception("error searching documents", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching documents: {exc}",
        ) from exc


@router.post(
    "/rag_query",
    status_code=status.HTTP_200_OK,
    summary="Answer a query using the configured RAG agent",
)
async def rag_query(
    request: RagQueryRequest,
    rag_agent: RagAgentDep,
) -> RagQueryResponse:
    """Resuelve una consulta usando el agente RAG configurado.

    Este endpoint no hace retrieval directamente; solo traduce la solicitud HTTP
    y delega en ``RAGAgent`` la recuperacion de contexto y armado de respuesta.
    """
    try:
        result = rag_agent.answer_with_context(
            question=request.question,
            top_k=request.top_k,
            department=request.department,
        )
        return RagQueryResponse(**result)
    except Exception as exc:
        logger.exception("error executing rag query", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing rag query: {exc}",
        ) from exc
