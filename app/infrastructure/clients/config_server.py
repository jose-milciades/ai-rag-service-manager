"""Startup-only client for Spring Config Server.

Este cliente existe exclusivamente para la fase de arranque del microservicio.
Se consulta una vez durante ``lifespan`` para obtener o reportar configuracion
remota. No se usa en cada request y no participa en el flujo normal de negocio.

El resultado actual se almacena como estado informativo en ``application.state``
para exponerlo en readiness y para diagnostico operacional.
"""

import logging
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class ConfigServerClient:
    """Cliente tecnico para consultar Spring Config Server durante el startup."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def fetch_config(self) -> dict[str, Any]:
        """Consulta configuracion remota una sola vez al iniciar la aplicacion.

        Si la integracion esta deshabilitada, retorna un estado neutral. Si la
        consulta falla, retorna metadatos del error sin impedir el arranque.
        """
        if not self._settings.use_spring_cloud_config or not self._settings.spring_cloud_config_uri:
            return {"enabled": False, "loaded": False}

        url = (
            f"{self._settings.spring_cloud_config_uri.rstrip('/')}"
            f"/{self._settings.app_name}/{self._settings.spring_profiles_active}"
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()

            payload = response.json()
            property_sources = payload.get("propertySources", [])
            resolved: dict[str, Any] = {}
            for source in reversed(property_sources):
                resolved.update(source.get("source", {}))

            logger.info("spring config loaded from %s", url)
            return {
                "enabled": True,
                "loaded": True,
                "name": payload.get("name", self._settings.app_name),
                "profile": payload.get("profiles", [self._settings.spring_profiles_active]),
                "label": payload.get("label"),
                "property_sources": len(property_sources),
                "resolved_keys": sorted(resolved.keys()),
            }
        except Exception as exc:  # noqa: BLE001 - integracion opcional de arranque: cualquier falla se reporta y no debe impedir el startup
            logger.warning("spring config could not be loaded from %s: %s", url, exc)
            return {
                "enabled": True,
                "loaded": False,
                "error": str(exc),
            }
