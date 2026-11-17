from pydantic import BaseModel, Field

from app.core.schema import get_camel_case_config


class UploadFileResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool = Field(...)


class ChunkUploadResponse(BaseModel):
    model_config = get_camel_case_config()

    consolidated: bool = Field(
        ..., description="true en el chunk que completa el upload y dispara la consolidacion"
    )
    success: bool = Field(
        ..., description="Resultado de la consolidacion (siempre true si consolidated=false)"
    )


class UploadPublicFileResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool = Field(...)
    url: str | None = Field(default=None)


class FileResponse(BaseModel):
    model_config = get_camel_case_config()

    array_bytes: list[int] | None = Field(default=None)
    application: str | None = Field(default=None)
    extension: str | None = Field(default=None)
    name: str | None = Field(default=None)
    base64: str | None = Field(default=None)


class StorageInfoResponse(BaseModel):
    """Storage al que esta conectado el servicio (sin secretos)."""

    model_config = get_camel_case_config()

    provider: str = Field(..., description="Proveedor de storage (GCS)")
    bucket: str | None = Field(default=None, description="Bucket por defecto configurado")
    environment: str = Field(..., description="RAG_ENVIRONMENT del servicio")


class DeleteFileResponse(BaseModel):
    model_config = get_camel_case_config()

    deleted: bool = Field(..., description="true si el objeto existia y se elimino")
    existed: bool = Field(..., description="false si el objeto ya no existia (404, idempotente)")
    storage: StorageInfoResponse = Field(..., description="Storage efectivamente usado")
