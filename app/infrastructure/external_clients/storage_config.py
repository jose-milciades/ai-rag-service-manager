"""Configuracion de acceso a Google Cloud Storage."""

import json
from pathlib import Path
import os

from app.core.config import Settings


class StorageConfig:
    """Adaptador de configuracion compatible con otros microservicios."""

    _default_credentials_file = Path("edward-creds.json")

    def __init__(self, settings: Settings) -> None:
        self.google_json_cred = settings.google_application_credentials or self._get_default_credentials_path()
        self.project_id = settings.storage_project_id or self._get_project_id_from_credentials_file()
        self.default_bucket_name = settings.storage_default_bucket_name

    def apply_credentials_environment(self) -> None:
        if self.google_json_cred:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.google_json_cred

    def credentials_file_exists(self) -> bool:
        return bool(self.google_json_cred and Path(self.google_json_cred).exists())

    def _get_default_credentials_path(self) -> str | None:
        if self._default_credentials_file.exists():
            return str(self._default_credentials_file)
        return None

    def _get_project_id_from_credentials_file(self) -> str | None:
        if not self.google_json_cred:
            return None

        credentials_path = Path(self.google_json_cred)
        if not credentials_path.exists():
            return None

        try:
            credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        project_id = credentials.get("project_id")
        return project_id if isinstance(project_id, str) and project_id else None