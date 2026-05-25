from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router_controller import api_router
from app.api.dependencies.services import get_storage_client
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.external_clients.config_server import ConfigServerClient
from app.infrastructure.external_clients.eureka import EurekaRegistrar


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application startup and shutdown orchestration.

    En startup se inicializan integraciones operacionales. ``ConfigServerClient``
    se usa solo aqui, como dependencia de arranque, para consultar una vez el
    estado/configuracion remota. No se reutiliza por request.
    """
    configure_logging()
    logger = get_logger(__name__)
    settings = get_settings()
    logger.info("starting %s in %s", settings.app_name, settings.app_env)

    config_server_client = ConfigServerClient(settings=settings)
    eureka_registrar = EurekaRegistrar(settings=settings)

    # Config Server es una integracion de arranque: se consulta una sola vez y
    # su resultado se conserva solo como estado informativo/operacional.
    application.state.remote_config = await config_server_client.fetch_config()
    application.state.eureka = await eureka_registrar.register()
    application.state.eureka_registrar = eureka_registrar
    get_storage_client().startup_event()

    yield

    await eureka_registrar.stop()
    logger.info("stopping %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Microservicio para administrar configuraciones de servicios RAG.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router, prefix=settings.api_prefix)

    @application.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "environment": settings.app_env,
            "api_prefix": settings.api_prefix,
            "docs": "/docs",
        }

    return application


app = create_app()


def run() -> None:
    """Inicia Uvicorn usando host y puerto resueltos desde Settings."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
