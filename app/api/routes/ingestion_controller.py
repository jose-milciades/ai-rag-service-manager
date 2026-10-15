"""HTTP controller de ingesta de texto plano (/ingestion)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.services import get_retrieval_service
from app.schemas.retrieval import IngestTextRequest, IngestTextResponse
from app.services.retrieval.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
RetrievalServiceDep = Annotated[RetrievalService, Depends(get_retrieval_service)]


@router.post("/text", status_code=status.HTTP_200_OK, summary="Index plain text")
async def ingest_text(
    request: IngestTextRequest, service: RetrievalServiceDep
) -> IngestTextResponse:
    """Indexa texto plano como documento (opcionalmente reemplazando el anterior)."""
    try:
        return service.ingest_text(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("error ingesting text")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error ingesting text: {exc}"
        ) from exc
