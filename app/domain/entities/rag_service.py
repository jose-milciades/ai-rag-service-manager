from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class RagServiceStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"


@dataclass(slots=True)
class RagService:
    service_id: str
    name: str
    description: str | None
    llm_provider: str
    chat_model: str
    embedding_model: str
    vector_backend: str
    base_url: str | None
    status: RagServiceStatus = RagServiceStatus.DRAFT
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
