"""HTTP controller de extraccion de texto sin indexar (/extraction)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.services import get_retrieval_service
from app.schemas.retrieval import ExtractTextRequest, ExtractTextResponse
from app.services.embedding.text_extractors import NeedsOcrError, UnsupportedFormatError
from app.services.retrieval.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extraction", tags=["extraction"])
RetrievalServiceDep = Annotated[RetrievalService, Depends(get_retrieval_service)]


@router.post("/text", status_code=status.HTTP_200_OK, summary="Extract text without indexing")
async def extract_text(
    request: ExtractTextRequest, service: RetrievalServiceDep
) -> ExtractTextResponse:
    """Extrae texto (con OCR si hace falta) de un archivo, sin crear vectores."""
    try:
        return service.extract_text(request)
    except UnsupportedFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except (ValueError, NeedsOcrError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("error extracting text")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting text: {exc}",
        ) from exc
