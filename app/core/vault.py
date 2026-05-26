import os
import hvac

from functools import lru_cache


class VaultClient:
    def __init__(self):

        self.client = hvac.Client(
            url=os.getenv("VAULT_ADDR"),
            token=os.getenv("VAULT_TOKEN"),
        )
        if not self.client.is_authenticated():
            raise Exception("Vault authentication failed")

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
