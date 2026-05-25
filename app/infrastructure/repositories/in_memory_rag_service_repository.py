from app.domain.entities.rag_service import RagService
from app.domain.repositories.rag_service_repository import RagServiceRepository


class InMemoryRagServiceRepository(RagServiceRepository):
    def __init__(self) -> None:
        self._services: dict[str, RagService] = {}

    async def list(self) -> list[RagService]:
        return sorted(self._services.values(), key=lambda item: item.created_at)

    async def get(self, service_id: str) -> RagService | None:
        return self._services.get(service_id)

    async def get_by_name(self, name: str) -> RagService | None:
        lowered_name = name.strip().lower()
        for service in self._services.values():
            if service.name.strip().lower() == lowered_name:
                return service
        return None

    async def save(self, service: RagService) -> RagService:
        self._services[service.service_id] = service
        return service

    async def delete(self, service_id: str) -> None:
        self._services.pop(service_id, None)
