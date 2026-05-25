from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.rag_service import RagServiceStatus


class RagServiceBase(BaseModel):
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
    status: RagServiceStatus


class RagServiceResponse(RagServiceBase):
    model_config = ConfigDict(from_attributes=True)

    service_id: str
    status: RagServiceStatus
    created_at: datetime
    updated_at: datetime


class RagServiceListResponse(BaseModel):
    items: list[RagServiceResponse]
    total: int
