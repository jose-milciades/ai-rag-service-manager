from pydantic import BaseModel, Field

from app.core.schema import get_camel_case_config


class UploadFileResponse(BaseModel):
    model_config = get_camel_case_config()

    success: bool = Field(...)


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
