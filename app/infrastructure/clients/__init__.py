"""Infrastructure clients package.

Convencion de capas para este proyecto:

- ``services`` orquesta casos de uso y reglas de aplicacion
- ``infrastructure.clients`` encapsula SDKs, HTTP clients e integraciones externas
- ``core`` concentra configuracion transversal y wiring comun

Este paquete existe para que las integraciones externas tengan una ubicacion
estable y explicita sin mezclar detalles tecnicos con la capa de servicios.
"""

from app.infrastructure.clients.config_server import ConfigServerClient
from app.infrastructure.clients.eureka import EurekaRegistrar
from app.infrastructure.clients.storage_client import StorageClient
from app.infrastructure.clients.storage_config import StorageConfig

__all__ = [
    "ConfigServerClient",
    "EurekaRegistrar",
    "StorageClient",
    "StorageConfig",
]
