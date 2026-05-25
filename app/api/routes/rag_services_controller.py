"""HTTP controller for RAG service management.

Este archivo pertenece a la capa de API y actua como controller, no como service.
Su responsabilidad es:

- definir rutas HTTP
- validar entrada y salida mediante schemas
- resolver dependencias de FastAPI
- delegar la logica de negocio a ``RagServiceManager``

La logica de negocio real vive en ``app/services/rag_service.py``.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies.services import get_rag_service_manager
from app.schemas.rag_service import (
    RagServiceCreate,
    RagServiceListResponse,
    RagServiceResponse,
    RagServiceStatusUpdate,
    RagServiceUpdate,
)
from app.services.rag_service import RagServiceManager

router = APIRouter(prefix="/rag-services", tags=["rag-services"])

# Alias de dependencia para no repetir ``Depends(...)`` en cada handler.
RagServiceManagerDep = Annotated[RagServiceManager, Depends(get_rag_service_manager)]


@router.get("")
async def list_rag_services(manager: RagServiceManagerDep) -> RagServiceListResponse:
    """Lista todos los registros administrados por el service.

    El controller solo recibe la solicitud HTTP y transforma las entidades del
    dominio a ``RagServiceResponse`` para la respuesta.
    """
    services = await manager.list_services()
    return RagServiceListResponse(
        items=[RagServiceResponse.model_validate(service) for service in services],
        total=len(services),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_rag_service(
    payload: RagServiceCreate,
    manager: RagServiceManagerDep,
) -> RagServiceResponse:
    """Crea un nuevo registro de configuracion RAG.

    La validacion estructural del request la hace FastAPI/Pydantic; reglas como
    unicidad de nombre o estado permitido quedan delegadas al service.
    """
    service = await manager.create_service(payload)
    return RagServiceResponse.model_validate(service)


@router.get("/{service_id}")
async def get_rag_service(
    service_id: str,
    manager: RagServiceManagerDep,
) -> RagServiceResponse:
    """Obtiene un registro puntual por su identificador.

    Si el recurso no existe, la excepcion HTTP la emite el service para mantener
    la regla de acceso centralizada en una sola capa.
    """
    service = await manager.get_service(service_id)
    return RagServiceResponse.model_validate(service)


@router.put("/{service_id}")
async def update_rag_service(
    service_id: str,
    payload: RagServiceUpdate,
    manager: RagServiceManagerDep,
) -> RagServiceResponse:
    """Actualiza de forma completa un registro existente.

    Este endpoint representa un update completo del recurso; por eso recibe el
    schema ``RagServiceUpdate`` y delega al manager la sustitucion del estado.
    """
    service = await manager.update_service(service_id, payload)
    return RagServiceResponse.model_validate(service)


@router.patch("/{service_id}/status")
async def update_rag_service_status(
    service_id: str,
    payload: RagServiceStatusUpdate,
    manager: RagServiceManagerDep,
) -> RagServiceResponse:
    """Actualiza solo el estado del recurso.

    Este handler expone una mutacion parcial y deja la transicion de estado en
    manos del service.
    """
    service = await manager.update_status(service_id, payload.status)
    return RagServiceResponse.model_validate(service)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rag_service(
    service_id: str,
    manager: RagServiceManagerDep,
) -> Response:
    """Elimina un recurso por identificador.

    El controller no decide si el recurso existe ni como se borra; solo traduce
    la operacion a semantica HTTP 204 cuando el service completa la accion.
    """
    await manager.delete_service(service_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
