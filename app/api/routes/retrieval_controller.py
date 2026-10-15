"""HTTP controller de recuperacion (/retrieval): busqueda con filtros ricos y lectura de documento."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.services import get_retrieval_service
from app.schemas.retrieval import (
    RetrievalDocumentRequest,
    RetrievalDocumentResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from app.services.retrieval.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])
RetrievalServiceDep = Annotated[RetrievalService, Depends(get_retrieval_service)]


@router.post("/search", status_code=status.HTTP_200_OK, summary="Semantic search with rich filters")
async def search(
    request: RetrievalSearchRequest, service: RetrievalServiceDep
) -> RetrievalSearchResponse:
    """Busqueda semantica con operadores de filtro, texto completo y contexto unido."""
    try:
        return service.search(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("error in retrieval search")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error searching: {exc}"
        ) from exc


@router.post("/document", status_code=status.HTTP_200_OK, summary="Read the chunks of one document")
async def document(
    request: RetrievalDocumentRequest, service: RetrievalServiceDep
) -> RetrievalDocumentResponse:
    """Chunks de un documento ordenados, con rango opcional."""
    try:
        return service.document(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("error reading document chunks")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading document: {exc}",
        ) from exc
