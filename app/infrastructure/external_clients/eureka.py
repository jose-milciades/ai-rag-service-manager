"""Infrastructure client for Eureka service registration.

Este modulo encapsula el registro y el cierre del cliente Eureka. Su uso ocurre
en el ciclo de vida de la aplicacion y no en el flujo request/response normal.
"""

import asyncio
import logging
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)

try:
    import py_eureka_client.eureka_client as eureka_client
except ImportError:
    eureka_client = None


class EurekaRegistrar:
    """Encapsula registro, reintentos y shutdown del cliente Eureka."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._registered = False

    async def register(self) -> dict[str, Any]:
        """Intenta registrar la aplicacion en Eureka durante startup."""
        if not self._settings.eureka_enabled:
            return {"enabled": False, "registered": False}

        if eureka_client is None:
            logger.warning("py_eureka_client is not available")
            return {
                "enabled": True,
                "registered": False,
                "error": "py_eureka_client not installed",
            }

        for attempt in range(1, self._settings.eureka_register_max_retries + 1):
            try:
                logger.info("registering %s in Eureka (attempt %s)", self._settings.eureka_app_name, attempt)
                await eureka_client.init_async(
                    eureka_server=self._settings.eureka_server_url,
                    app_name=self._settings.eureka_app_name,
                    instance_port=self._settings.app_port,
                    instance_host=self._settings.eureka_instance_host,
                    instance_ip=self._settings.eureka_instance_ip,
                    instance_id=f"{self._settings.eureka_app_name}:{self._settings.app_port}",
                )
                self._registered = True
                return {
                    "enabled": True,
                    "registered": True,
                    "server": self._settings.eureka_server_url,
                }
            except Exception as exc:
                logger.error("error registering in Eureka: %s", exc)
                await asyncio.sleep(self._settings.eureka_register_retry_delay * attempt)

        return {
            "enabled": True,
            "registered": False,
            "error": "registration retries exhausted",
        }

    async def stop(self) -> None:
        """Detiene el cliente Eureka si quedo registrado previamente."""
        if self._registered and eureka_client is not None:
            try:
                await eureka_client.stop_async()
            except Exception as exc:
                logger.warning("error stopping Eureka client: %s", exc)
