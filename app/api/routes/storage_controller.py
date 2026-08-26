"""HTTP controller for migrated storage endpoints."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.services import get_storage_service
from app.schemas.storage import (
    ChunkUploadResponse,
    FileResponse,
    UploadFileResponse,
    UploadPublicFileResponse,
)
from app.services.storage_service import StorageService, VectorizationTrigger

router = APIRouter(prefix="/storage", tags=["storage"])

StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]


async def _vectorization_trigger_form(
    *,
    code_type_document: str | None = Form(default=None, alias="codeTypeDocument"),
    upload_content_bucket: bool | None = Form(default=None, alias="uploadContentBucket"),
    unique_code: str | None = Form(default=None, alias="uniqueCode"),
    id_document: str | None = Form(default=None, alias="idDocument"),
    background_tasks: BackgroundTasks,
) -> VectorizationTrigger:
    """Sub-dependencia que agrupa los campos opcionales de vectorizacion (P-10/P-11).

    ``BackgroundTasks`` puede declararse en cualquier nivel del arbol de
    dependencias de FastAPI, no solo en la funcion del endpoint -- por eso
    esto se puede resolver como una sola dependencia reusable en vez de
    repetir estos 5 parametros en cada endpoint (evita el warning S107 de
    Sonar por exceso de parametros).
    """
    return VectorizationTrigger(
        code_type_document=code_type_document,
        upload_content_bucket=upload_content_bucket,
        unique_code=unique_code,
        id_document=id_document,
        background_tasks=background_tasks,
    )


VectorizationTriggerDep = Annotated[VectorizationTrigger, Depends(_vectorization_trigger_form)]


@router.post(
    "/upload",
    status_code=status.HTTP_200_OK,
    response_model=UploadFileResponse,
)
async def upload_file(
    *,
    file: UploadFile = File(...),
    name: str = Form(...),
    bucket: str | None = Form(default=None),
    project_id: str | None = Form(default=None, alias="projectId"),
    vectorization: VectorizationTriggerDep,
    service: StorageServiceDep,
) -> UploadFileResponse:
    return await service.upload_file(
        file=file,
        name=name,
        bucket=bucket,
        project_id=project_id,
        vectorization=vectorization,
    )


@router.post("/chunk", status_code=status.HTTP_200_OK, response_model=ChunkUploadResponse)
async def upload_chunk(
    *,
    file: UploadFile = File(...),
    upload_id: str = Form(..., alias="uploadId"),
    chunk_index: int = Form(..., alias="chunkIndex"),
    total_chunks: int = Form(..., alias="totalChunks"),
    file_name: str = Form(..., alias="fileName"),
    name: str = Form(...),
    bucket: str | None = Form(default=None),
    project_id: str = Form(..., alias="projectId"),
    id_area: str | None = Form(default=None, alias="idArea"),
    vectorization: VectorizationTriggerDep,
    service: StorageServiceDep,
) -> ChunkUploadResponse:
    return await service.store_chunk(
        file=file,
        upload_id=upload_id,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        file_name=file_name,
        name=name,
        bucket=bucket,
        id_area=id_area,
        project_id=project_id,
        vectorization=vectorization,
    )


@router.get("/get", status_code=status.HTTP_200_OK)
async def get_file(
    *,
    name: str = Query(...),
    bucket: str | None = Query(default=None),
    service: StorageServiceDep,
) -> StreamingResponse:
    file_bytes, content_type = await service.get_file(name=name, bucket=bucket)
    headers = {"Content-Disposition": f"attachment;filename={name}"}
    return StreamingResponse(
        iter([file_bytes]),
        media_type=content_type or "application/octet-stream",
        headers=headers,
    )


@router.get(
    "/getFileByte",
    status_code=status.HTTP_200_OK,
    response_model=FileResponse,
)
async def get_file_byte(
    *,
    name: str = Query(...),
    bucket: str | None = Query(default=None),
    service: StorageServiceDep,
) -> FileResponse:
    return await service.get_file_byte(name=name, bucket=bucket)


@router.post(
    "/public-upload",
    status_code=status.HTTP_200_OK,
    response_model=UploadPublicFileResponse,
)
async def upload_public_file(
    *,
    file: UploadFile = File(...),
    name: str = Form(...),
    bucket: str | None = Form(default=None),
    project_id: str | None = Form(default=None, alias="projectId"),
    code_type_document: str | None = Form(default=None, alias="codeTypeDocument"),
    upload_content_bucket: bool | None = Form(default=None, alias="uploadContentBucket"),
    service: StorageServiceDep,
) -> UploadPublicFileResponse:
    return await service.upload_public_file(
        file=file,
        name=name,
        bucket=bucket,
        project_id=project_id,
        code_type_document=code_type_document,
        upload_content_bucket=upload_content_bucket,
    )
