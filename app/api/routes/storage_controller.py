"""HTTP controller for migrated storage endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.services import get_storage_service
from app.schemas.storage import FileResponse, UploadFileResponse, UploadPublicFileResponse
from app.services.storage_service import StorageService

router = APIRouter(prefix="/storage", tags=["storage"])

StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]


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
    code_type_document: str | None = Form(default=None, alias="codeTypeDocument"),
    upload_content_bucket: bool | None = Form(default=None, alias="uploadContentBucket"),
    service: StorageServiceDep,
) -> UploadFileResponse:
    return await service.upload_file(
        file=file,
        name=name,
        bucket=bucket,
        project_id=project_id,
        code_type_document=code_type_document,
        upload_content_bucket=upload_content_bucket,
    )


@router.post("/chunk", status_code=status.HTTP_200_OK)
async def upload_chunk(
    *,
    file: UploadFile = File(...),
    upload_id: str = Form(..., alias="uploadId"),
    chunk_index: int = Form(..., alias="chunkIndex"),
    total_chunks: int = Form(..., alias="totalChunks"),
    file_name: str = Form(..., alias="fileName"),
    name: str = Form(...),
    bucket: str = Form(...),
    project_id: str = Form(..., alias="projectId"),
    id_area: str | None = Form(default=None, alias="idArea"),
    service: StorageServiceDep,
) -> Response:
    await service.store_chunk(
        file=file,
        upload_id=upload_id,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        file_name=file_name,
        name=name,
        bucket=bucket,
        id_area=id_area,
        project_id=project_id,
    )
    return Response(status_code=status.HTTP_200_OK)


@router.get("/get", status_code=status.HTTP_200_OK)
async def get_file(
    *,
    name: str = Query(...),
    bucket: str = Query(...),
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
    bucket: str = Query(...),
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
