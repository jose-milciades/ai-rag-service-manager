import os
from functools import lru_cache

import hvac
import urllib3
from urllib3.exceptions import InsecureRequestWarning


def _is_truthy(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def is_vault_configured() -> bool:
    """Indica si se debe usar Vault, igual patron que ``EUREKA_ENABLED`` y
    ``USE_SPRING_CLOUD_CONFIG``: una variable explicita, no una inferencia
    por presencia de otras variables. Por defecto false, para que trabajo
    local no dependa de tener un Vault corriendo.

    Se usa antes de intentar construir un ``VaultClient`` (ver
    ``app.core.config.get_settings``). Si es true pero falta
    ``VAULT_ADDR``/``VAULT_TOKEN``, ``VaultClient`` falla fuerte con un
    mensaje claro lista lo que falta, en vez de caer en silencio a `.env`.
    """
    return _is_truthy(os.getenv("USE_VAULT_CONFIG"))


def _configure_tls_warning_suppression(vault_skip_verify: bool) -> None:
    if vault_skip_verify:
        urllib3.disable_warnings(InsecureRequestWarning)


class VaultClient:
    def __init__(self) -> None:
        vault_addr = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")
        vault_cacert = os.getenv("VAULT_CACERT")
        vault_skip_verify = _is_truthy(os.getenv("VAULT_SKIP_VERIFY"))

        missing_env_vars = [
            env_name
            for env_name, env_value in (("VAULT_ADDR", vault_addr), ("VAULT_TOKEN", vault_token))
            if not env_value
        ]

        if missing_env_vars:
            missing_values = ", ".join(missing_env_vars)
            raise ValueError(f"Missing Vault environment variables: {missing_values}")

        verify = False if vault_skip_verify else (vault_cacert or True)

        _configure_tls_warning_suppression(vault_skip_verify)

        self.client = hvac.Client(
            url=vault_addr,
            token=vault_token,
            verify=verify,
        )

        try:
            is_authenticated = self.client.is_authenticated()
        except Exception as exc:
            raise ValueError(
                f"Vault connection failed for VAULT_ADDR={vault_addr}. "
                "If Vault uses internal TLS, configure VAULT_CACERT or set "
                "VAULT_SKIP_VERIFY=true."
            ) from exc

        if not is_authenticated:
            raise ValueError(
                f"Vault authentication failed for VAULT_ADDR={vault_addr}. "
                "Verify that VAULT_TOKEN is valid and was injected into the container."
            )

    def get_secret(self, path: str) -> dict:

        response = self.client.secrets.kv.v2.read_secret_version(path=path)

        return response["data"]["data"]

    def load_configs(self, paths: list[str]) -> dict:

        config = {}

        for path in paths:
            secret = self.get_secret(path)
            config.update(secret)

        return config


@lru_cache
def get_vault_client() -> VaultClient:
    return VaultClient()
