"""Infrastructure client for external file retrieval.

Este cliente encapsula descargas desde ubicaciones externas como URLs o GCS.
No realiza transformaciones de negocio; solo devuelve bytes para que la capa de
servicios decida que hacer con ese contenido.
"""

import logging

import httpx

from app.core.config import Settings
from app.infrastructure.external_clients.storage_config import StorageConfig

logger = logging.getLogger(__name__)


class StorageClient:
    """Cliente tecnico para obtener archivos desde URL o bucket."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._config = StorageConfig(settings)
        self._client = None

    def startup_event(self) -> None:
        """Verifica de forma no bloqueante la configuracion de acceso a GCS."""
        if not self._config.default_bucket_name:
            logger.info("storage startup check skipped because no default bucket is configured")
            return

        try:
            bucket = self._get_bucket(self._config.default_bucket_name)
            logger.info("storage configured for bucket %s", bucket.name)
        except Exception as exc:
            logger.error("storage startup check failed: %s", exc)

    def download_from_bucket(self, filename: str, bucket_name: str | None = None) -> bytes:
        """Descarga un archivo desde GCS y retorna su contenido binario."""
        blob = self._get_bucket(bucket_name).blob(filename)
        if not blob.exists():
            raise FileNotFoundError(
                f"File {filename} not found in bucket {blob.bucket.name}"
            )

        logger.info("downloading %s from bucket %s", filename, blob.bucket.name)
        return blob.download_as_bytes()

    def download_from_url(self, url: str) -> bytes:
        """Descarga un archivo remoto via HTTP y retorna sus bytes."""
        logger.info("downloading file from url %s", url)
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        return response.content

    def _get_bucket(self, bucket_name: str | None):
        bucket_to_use = bucket_name or self._config.default_bucket_name
        if not bucket_to_use:
            raise ValueError("Bucket name is required for storage download")
        return self._get_client().bucket(bucket_to_use)

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is not installed") from exc

        self._config.apply_credentials_environment()
        client_kwargs = {}
        if self._config.project_id:
            client_kwargs["project"] = self._config.project_id
        self._client = storage.Client(**client_kwargs)
        return self._client
