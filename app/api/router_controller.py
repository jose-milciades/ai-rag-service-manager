"""API router composition layer.

Este modulo agrega los distintos controllers HTTP de la aplicacion y los expone
como un unico ``APIRouter`` que luego es incluido por ``app/main.py``.
"""

from fastapi import APIRouter

from app.api.routes import (
    embedding_controller,
    health_controller,
    rag_services_controller,
)

api_router = APIRouter()
api_router.include_router(health_controller.router)
api_router.include_router(rag_services_controller.router)
api_router.include_router(embedding_controller.router)
