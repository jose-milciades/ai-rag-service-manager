"""HTTP controller for migrated storage endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.services import get_storage_service
from app.schemas.storage import FileResponse, UploadFileResponse, UploadPublicFileResponse
from app.services.storage_service import StorageService

router = APIRouter(prefix="/storage", tags=["storage"])

StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]


def _resolve_request_value(request: Request, form_data: object, key: str) -> str | None:
    query_value = request.query_params.get(key)
    if query_value is not None:
        return query_value
    if hasattr(form_data, "get"):
        value = form_data.get(key)
        if isinstance(value, str):
            return value
    return None


@router.post(
    "/upload",
    status_code=status.HTTP_200_OK,
    response_model=UploadFileResponse,
)
async def upload_file(
    file: UploadFile = File(...),
    name: str = Form(...),
    bucket: str | None = Form(default=None),
    project_id: str | None = Form(default=None, alias="projectId"),
    code_type_document: str | None = Form(default=None, alias="codeTypeDocument"),
    upload_content_bucket: bool | None = Form(default=None, alias="uploadContentBucket"),
    service: StorageServiceDep = None,
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
    request: Request,
    service: StorageServiceDep = None,
) -> Response:
    form_data = await request.form()
    file = form_data.get("file")
    if not isinstance(file, UploadFile):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'file' is required",
        )

    upload_id = _resolve_request_value(request, form_data, "uploadId")
    chunk_index = _resolve_request_value(request, form_data, "chunkIndex")
    total_chunks = _resolve_request_value(request, form_data, "totalChunks")
    file_name = _resolve_request_value(request, form_data, "fileName")
    name = _resolve_request_value(request, form_data, "name")
    bucket = _resolve_request_value(request, form_data, "bucket")
    id_area = _resolve_request_value(request, form_data, "idArea")
    project_id = _resolve_request_value(request, form_data, "projectId")

    required_values = {
        "uploadId": upload_id,
        "chunkIndex": chunk_index,
        "totalChunks": total_chunks,
        "fileName": file_name,
        "name": name,
        "bucket": bucket,
        "projectId": project_id,
    }
    missing_fields = [key for key, value in required_values.items() if value in (None, "")]
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required fields: {', '.join(missing_fields)}",
        )

    await service.store_chunk(
        file=file,
        upload_id=upload_id,
        chunk_index=int(chunk_index),
        total_chunks=int(total_chunks),
        file_name=file_name,
        name=name,
        bucket=bucket,
        id_area=id_area,
        project_id=project_id,
    )
    return Response(status_code=status.HTTP_200_OK)


@router.get("/get", status_code=status.HTTP_200_OK)
async def get_file(
    name: str = Query(...),
    bucket: str = Query(...),
    service: StorageServiceDep = None,
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
    name: str = Query(...),
    bucket: str = Query(...),
    service: StorageServiceDep = None,
) -> FileResponse:
    return await service.get_file_byte(name=name, bucket=bucket)


@router.post(
    "/public-upload",
    status_code=status.HTTP_200_OK,
    response_model=UploadPublicFileResponse,
)
async def upload_public_file(
    file: UploadFile = File(...),
    name: str = Form(...),
    bucket: str | None = Form(default=None),
    project_id: str | None = Form(default=None, alias="projectId"),
    code_type_document: str | None = Form(default=None, alias="codeTypeDocument"),
    upload_content_bucket: bool | None = Form(default=None, alias="uploadContentBucket"),
    service: StorageServiceDep = None,
) -> UploadPublicFileResponse:
    return await service.upload_public_file(
        file=file,
        name=name,
        bucket=bucket,
        project_id=project_id,
        code_type_document=code_type_document,
        upload_content_bucket=upload_content_bucket,
    )