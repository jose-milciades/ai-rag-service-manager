from datetime import datetime

from pydantic import BaseModel, Field

from app.core.schema import get_camel_case_config
from app.domain.entities.rag_service import RagServiceStatus


class RagServiceBase(BaseModel):
    model_config = get_camel_case_config()

    name: str = Field(min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    llm_provider: str = Field(min_length=2, max_length=50)
    chat_model: str = Field(min_length=2, max_length=100)
    embedding_model: str = Field(min_length=2, max_length=100)
    vector_backend: str = Field(min_length=2, max_length=50)
    base_url: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class RagServiceCreate(RagServiceBase):
    status: RagServiceStatus = RagServiceStatus.DRAFT


class RagServiceUpdate(RagServiceBase):
    status: RagServiceStatus


class RagServiceStatusUpdate(BaseModel):
    model_config = get_camel_case_config()

    status: RagServiceStatus


class RagServiceResponse(RagServiceBase):
    model_config = get_camel_case_config(from_attributes=True)

    service_id: str
    status: RagServiceStatus
    created_at: datetime
    updated_at: datetime


class RagServiceListResponse(BaseModel):
    model_config = get_camel_case_config()

    items: list[RagServiceResponse]
    total: int
