"""Health check controller.

Expone endpoints livianos para liveness y readiness. El readiness incluye una
vista simple del estado de integraciones levantadas en el startup y falla con
503 si alguna integracion marcada como critica no pudo completarse.
"""

from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])

# Clave que indica exito por cada integracion, tal como la reportan
# ConfigServerClient.fetch_config() y EurekaRegistrar.register() en
# app.state. Si una integracion no llega a inicializarse (variables ausentes
# => *_enabled=False por default en Settings), directamente no participa del
# calculo: no queda "enabled" y por lo tanto no puede fallar.
_DEPENDENCY_SUCCESS_KEYS = {
    "config_server": "loaded",
    "eureka": "registered",
}


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Indica que el proceso esta vivo."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness(request: Request, response: Response) -> dict[str, Any]:
    """Indica si la aplicacion puede servir trafico.

    Una integracion solo se reporta como fallida si esta habilitada
    (``enabled``) y no logro completarse (``loaded``/``registered`` en
    false). Si esta deshabilitada -tipicamente porque sus variables de
    entorno no llegaron- no participa del calculo.

    De las integraciones fallidas, solo las listadas en
    ``settings.readiness_critical_dependencies`` (env var
    ``READINESS_CRITICAL_DEPENDENCIES``, CSV) escalan a 503. El resto queda
    reportado en ``failed_dependencies`` para diagnostico sin bloquear el
    trafico.
    """
    settings = get_settings()
    critical_dependencies = {
        name.strip() for name in settings.readiness_critical_dependencies.split(",") if name.strip()
    }

    dependency_states = {
        "config_server": getattr(request.app.state, "remote_config", {}),
        "eureka": getattr(request.app.state, "eureka", {}),
    }

    failed_dependencies = [
        name
        for name, state in dependency_states.items()
        if state.get("enabled") and not state.get(_DEPENDENCY_SUCCESS_KEYS[name])
    ]
    blocking_failures = [name for name in failed_dependencies if name in critical_dependencies]

    is_ready = not blocking_failures
    response.status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "not_ready",
        "service": settings.app_name,
        "environment": settings.app_env,
        "failed_dependencies": failed_dependencies,
        "blocking_failures": blocking_failures,
        "integrations": dependency_states,
    }
