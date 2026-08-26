"""Storage-specific configuration adapter.

La fuente de verdad sigue siendo ``app.core.config.Settings``. Este adaptador
solo concentra los parametros tecnicos de storage para evitar que queden
dispersos entre servicios, clients y wiring.
"""

import json
from typing import Any

from app.core.config import Settings


class StorageConfig:
    """Configuracion normalizada para integraciones de storage."""

    def __init__(self, settings: Settings) -> None:
        self.google_json_cred = settings.google_creds_json
        self.credentials_info = self._load_credentials_info()
        self.default_bucket_name = settings.storage_default_bucket_name
        self.public_bucket_name = settings.storage_public_bucket_name
        self.project_id = (
            settings.storage_project_id or self._get_project_id_from_credentials_info()
        )
        self.chunk_upload_temp_dir = settings.storage_chunk_upload_temp_dir
        self._validate_credentials_configuration()

    def has_credentials_info(self) -> bool:
        return self.credentials_info is not None

    def _get_project_id_from_credentials_info(self) -> str | None:
        if not self.credentials_info:
            return None

        project_id = self.credentials_info.get("project_id")
        return project_id if isinstance(project_id, str) and project_id else None

    def _load_credentials_info(self) -> dict[str, Any] | None:
        if not self.google_json_cred:
            return None

        try:
            credentials = json.loads(self.google_json_cred)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_CREDS_JSON must contain a valid JSON object") from exc

        if not isinstance(credentials, dict):
            raise TypeError("GOOGLE_CREDS_JSON must contain a JSON object")

        return credentials

    def _validate_credentials_configuration(self) -> None:
        if self.google_json_cred and not self.project_id:
            raise ValueError(
                "Storage credentials require project_id in GOOGLE_CREDS_JSON or STORAGE_PROJECT_ID"
            )
