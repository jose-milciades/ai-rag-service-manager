import os
import hvac

from functools import lru_cache


class VaultClient:
    def __init__(self):
        vault_addr = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")

        missing_env_vars = [
            env_name
            for env_name, env_value in (("VAULT_ADDR", vault_addr), ("VAULT_TOKEN", vault_token))
            if not env_value
        ]

        if missing_env_vars:
            missing_values = ", ".join(missing_env_vars)
            raise ValueError(f"Missing Vault environment variables: {missing_values}")

        self.client = hvac.Client(
            url=vault_addr,
            token=vault_token,
        )
        if not self.client.is_authenticated():
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
def get_vault_client():
    return VaultClient()
