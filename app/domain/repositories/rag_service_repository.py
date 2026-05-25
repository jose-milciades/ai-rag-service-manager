from abc import ABC, abstractmethod

from app.domain.entities.rag_service import RagService


class RagServiceRepository(ABC):
    @abstractmethod
    async def list(self) -> list[RagService]:
        raise NotImplementedError

    @abstractmethod
    async def get(self, service_id: str) -> RagService | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_name(self, name: str) -> RagService | None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, service: RagService) -> RagService:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, service_id: str) -> None:
        raise NotImplementedError
