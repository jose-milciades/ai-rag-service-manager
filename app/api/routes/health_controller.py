"""Health check controller.

Expone endpoints livianos para liveness y readiness. El readiness incluye una
vista simple del estado de integraciones levantadas en el startup.
"""

from typing import Any

from fastapi import APIRouter, Request

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Indica que el proceso esta vivo."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness(request: Request) -> dict[str, Any]:
    """Indica que la aplicacion termino su inicializacion basica."""
    settings = get_settings()
    return {
        "status": "ready",
        "service": settings.app_name,
        "environment": settings.app_env,
        "integrations": {
            "config_server": getattr(request.app.state, "remote_config", {}),
            "eureka": getattr(request.app.state, "eureka", {}),
        },
    }
