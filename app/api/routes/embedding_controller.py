"""HTTP controller for document embedding operations.

Este archivo pertenece a la capa de API. Su rol es exponer endpoints HTTP para
indexacion, consulta y recuperacion de contexto documental.

No implementa logica de negocio compleja. Todo el trabajo real se delega a
``DocumentEmbeddingService``.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status

from app.api.dependencies.services import get_document_embedding_service
from app.schemas.embedding import (
    DeleteDocumentVecstoreRequest,
    DeleteDocumentVecstoreResponse,
    DeleteIndexVecstoreRequest,
    GetEmbeddingsByUniqueCodeRequest,
    GetEmbeddingsByUniqueCodeResponse,
    ListDocumentsRequest,
    ListDocumentsResponse,
    OperationStatusResponse,
    SaveDocumentVecstoreRequest,
    SaveDocumentVecstoreResponse,
    SearchSimilarDocumentsRequest,
    SearchSimilarDocumentsResponse,
    UniqueCodeDocumentResponse,
)
from app.services.embedding.document_embedding_service import DocumentEmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embedding", tags=["embedding"])

# Dependencias compartidas de FastAPI para mantener handlers mas legibles.
EmbeddingServiceDep = Annotated[
    DocumentEmbeddingService,
    Depends(get_document_embedding_service),
]


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
        logger.exception("error saving document to vecstore")
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
        logger.exception("error deleting index")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting index: {exc}",
        ) from exc


@router.post(
    "/delete_document",
    status_code=status.HTTP_200_OK,
    summary="Delete a single document from a vector store index",
)
async def delete_document(
    request: DeleteDocumentVecstoreRequest,
    service: EmbeddingServiceDep,
) -> DeleteDocumentVecstoreResponse:
    """Elimina un unico documento (todos sus chunks) sin afectar el resto del indice.

    Complementa a ``/delete_index_vecstore`` (que borra la coleccion completa)
    para el caso de uso que hoy usa Java via ``deleteEmbeddingDocument`` — ver
    pendientes.md P-22. Se ejecuta sincrono porque, a diferencia de borrar una
    coleccion entera, es una operacion acotada por filtro.
    """
    try:
        result = service.delete_document(
            index_name=request.index_vecstore,
            id_document=request.id_document,
        )
        return DeleteDocumentVecstoreResponse(**result)
    except Exception as exc:
        logger.exception("error deleting document")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting document: {exc}",
        ) from exc


@router.post(
    "/list_unique_code_documents",
    status_code=status.HTTP_200_OK,
    summary="List a lightweight summary of unique documents in a namespace",
)
async def list_unique_code_documents(
    service: EmbeddingServiceDep,
    namespace: Annotated[str, Body(..., description="Nombre del índice/colección")],
) -> list[UniqueCodeDocumentResponse]:
    """Devuelve un listado liviano (namespace/codigo/fileName/id/nombreDocumento).

    Contrato pensado para ser un reemplazo directo de ``getListUniqueCodeDocuments``
    en el micro Java origen — ver pendientes.md P-23. El body es un string JSON
    plano (no un objeto) a propósito, para que Java pueda apuntar la URL a este
    servicio sin tener que cambiar cómo arma el request.
    """
    try:
        results = service.list_unique_code_documents(namespace=namespace)
        return [UniqueCodeDocumentResponse(**item) for item in results]
    except Exception as exc:
        logger.exception("error listing unique code documents")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing unique code documents: {exc}",
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
        logger.exception("error listing documents")
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
        logger.exception("error getting embeddings")
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
        logger.exception("error searching documents")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching documents: {exc}",
        ) from exc
