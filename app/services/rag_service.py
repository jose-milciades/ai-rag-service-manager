"""Application service for managing RAG service definitions.

Este modulo pertenece a la capa de servicios de aplicacion. No expone HTTP ni
conoce detalles de FastAPI mas alla del uso pragmatica de ``HTTPException`` para
propagar errores consistentes hacia la API.

Su responsabilidad es orquestar reglas de negocio sobre la entidad
``RagService`` y persistir cambios a traves del contrato
``RagServiceRepository``.
"""

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from app.domain.entities.rag_service import RagService, RagServiceStatus
from app.domain.repositories.rag_service_repository import RagServiceRepository
from app.schemas.rag_service import RagServiceCreate, RagServiceUpdate


class RagServiceManager:
    """Service de aplicacion para CRUD y reglas simples de configuraciones RAG."""

    def __init__(self, repository: RagServiceRepository) -> None:
        self._repository = repository

    async def list_services(self) -> list[RagService]:
        """Retorna todos los servicios configurados."""
        return await self._repository.list()

    async def get_service(self, service_id: str) -> RagService:
        """Busca un servicio por id y falla con 404 si no existe."""
        service = await self._repository.get(service_id)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"RAG service '{service_id}' no existe.",
            )
        return service

    async def create_service(self, payload: RagServiceCreate) -> RagService:
        """Crea una nueva definicion de servicio verificando unicidad por nombre."""
        await self._ensure_name_is_unique(payload.name)
        service = RagService(
            service_id=str(uuid4()),
            name=payload.name,
            description=payload.description,
            llm_provider=payload.llm_provider,
            chat_model=payload.chat_model,
            embedding_model=payload.embedding_model,
            vector_backend=payload.vector_backend,
            base_url=payload.base_url,
            status=payload.status,
            metadata=payload.metadata,
        )
        return await self._repository.save(service)

    async def update_service(self, service_id: str, payload: RagServiceUpdate) -> RagService:
        """Actualiza completamente un servicio existente."""
        current = await self.get_service(service_id)
        if current.name != payload.name:
            await self._ensure_name_is_unique(payload.name)

        updated = replace(
            current,
            name=payload.name,
            description=payload.description,
            llm_provider=payload.llm_provider,
            chat_model=payload.chat_model,
            embedding_model=payload.embedding_model,
            vector_backend=payload.vector_backend,
            base_url=payload.base_url,
            status=payload.status,
            metadata=payload.metadata,
            updated_at=datetime.now(timezone.utc),
        )
        return await self._repository.save(updated)

    async def update_status(self, service_id: str, status_value: RagServiceStatus) -> RagService:
        """Actualiza solo el estado del servicio."""
        current = await self.get_service(service_id)
        updated = replace(current, status=status_value, updated_at=datetime.now(timezone.utc))
        return await self._repository.save(updated)

    async def delete_service(self, service_id: str) -> None:
        """Elimina un servicio si existe."""
        await self.get_service(service_id)
        await self._repository.delete(service_id)

    async def _ensure_name_is_unique(self, name: str) -> None:
        """Evita colisiones funcionales de nombre en la configuracion administrada."""
        existing = await self._repository.get_by_name(name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un RAG service con el nombre '{name}'.",
            )
