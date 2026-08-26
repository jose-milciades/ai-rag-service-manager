"""Infrastructure client for storage and remote file retrieval.

Este cliente encapsula operaciones tecnicas contra Google Cloud Storage y
descargas HTTP puntuales. No contiene reglas de negocio ni decisiones de API.
"""

import ipaddress
import logging
import mimetypes
import socket
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.infrastructure.clients.storage_config import StorageConfig

logger = logging.getLogger(__name__)


def _ensure_public_http_url(url: str) -> None:
    """Bloquea esquemas y destinos que habilitarian SSRF via descarga remota.

    Rechaza esquemas distintos de http/https y cualquier hostname que resuelva
    a un rango de IP privado, loopback, link-local, reservado o multicast.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme for download: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Download URL must include a hostname")

    try:
        resolved_ips = {info[4][0] for info in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host {hostname!r}") from exc

    for raw_ip in resolved_ips:
        address = ipaddress.ip_address(raw_ip)
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise ValueError(
                f"Downloads targeting private/internal addresses are not allowed: {raw_ip}"
            )


class StorageClient:
    """Cliente tecnico para obtener y subir archivos a storage externo."""

    def __init__(self, config: StorageConfig) -> None:
        self._config = config
        self._client = None

    def startup_event(self) -> None:
        """Verifica de forma no bloqueante la configuracion de acceso a GCS."""
        if not self._config.default_bucket_name:
            logger.info("storage startup check skipped because no default bucket is configured")
            return

        try:
            bucket = self._get_bucket(self._config.default_bucket_name)
            logger.info("storage configured for bucket %s", bucket.name)
        except Exception as exc:  # noqa: BLE001 - chequeo de arranque no bloqueante: cualquier falla se reporta y no debe impedir el startup
            logger.error("storage startup check failed: %s", exc)

    def download_from_bucket(self, filename: str, bucket_name: str | None = None) -> bytes:
        """Descarga un archivo desde GCS y retorna su contenido binario."""
        blob = self._get_bucket(bucket_name).blob(filename)
        if not blob.exists():
            raise FileNotFoundError(f"File {filename} not found in bucket {blob.bucket.name}")

        logger.info("downloading %s from bucket %s", filename, blob.bucket.name)
        return blob.download_as_bytes()

    def download_with_metadata(
        self,
        filename: str,
        bucket_name: str | None = None,
    ) -> tuple[bytes, str | None]:
        """Descarga un archivo desde GCS junto con su content type."""
        blob = self._get_bucket(bucket_name).blob(filename)
        if not blob.exists():
            raise FileNotFoundError(f"File {filename} not found in bucket {blob.bucket.name}")

        logger.info("downloading %s with metadata from bucket %s", filename, blob.bucket.name)
        blob.reload()
        return blob.download_as_bytes(), blob.content_type

    def upload_bytes(
        self,
        file_bytes: bytes,
        file_name: str | None,
        content_type: str | None,
        storage_name: str,
        bucket_name: str | None = None,
    ) -> bool:
        """Sube bytes a GCS replicando el flujo base de storage del micro Java."""
        blob = self._get_bucket(bucket_name).blob(storage_name)
        resolved_content_type = self._resolve_content_type(file_name, storage_name, content_type)
        try:
            blob.upload_from_string(
                file_bytes,
                content_type=resolved_content_type or "application/octet-stream",
            )
            return True
        except Exception as exc:  # noqa: BLE001 - operacion tecnica de GCS: la falla se convierte en success=False para el llamador
            logger.error("storage upload failed for %s: %s", storage_name, exc)
            return False

    def upload_public_bytes(
        self,
        file_bytes: bytes,
        content_type: str | None,
    ) -> tuple[bool, str | None]:
        """Sube bytes al bucket publico configurado y retorna la URL publica."""
        public_bucket_name = self._config.public_bucket_name
        if not public_bucket_name:
            logger.error("storage public upload failed because no public bucket is configured")
            return False, None

        blob_name = str(uuid4())
        blob = self._get_bucket(public_bucket_name).blob(blob_name)
        try:
            blob.upload_from_string(file_bytes, content_type=content_type)
            return True, f"https://storage.googleapis.com/{public_bucket_name}/{blob_name}"
        except Exception as exc:  # noqa: BLE001 - operacion tecnica de GCS: la falla se convierte en success=False para el llamador
            logger.error("public storage upload failed for %s: %s", blob_name, exc)
            return False, None

    def download_from_url(self, url: str) -> bytes:
        """Descarga un archivo remoto via HTTP y retorna sus bytes.

        Valida el destino contra SSRF antes de emitir la solicitud: ver
        ``_ensure_public_http_url``.
        """
        _ensure_public_http_url(url)
        logger.info("downloading file from url %s", url)
        response = httpx.get(url, timeout=30.0, follow_redirects=False)
        response.raise_for_status()
        return response.content

    def _get_bucket(self, bucket_name: str | None) -> Any:
        # google-cloud-storage no publica marcador py.typed (ver
        # pyproject.toml [[tool.mypy.overrides]]); el tipo real es
        # google.cloud.storage.Bucket, tratado como Any por falta de stubs.
        bucket_to_use = bucket_name or self._config.default_bucket_name
        if not bucket_to_use:
            raise ValueError("Bucket name is required for storage download")
        return self._get_client().bucket(bucket_to_use)

    def _resolve_content_type(
        self,
        file_name: str | None,
        storage_name: str,
        content_type: str | None,
    ) -> str | None:
        if content_type and content_type.strip():
            return content_type

        resolved, _ = mimetypes.guess_type(file_name or storage_name)
        return resolved

    def _get_client(self) -> Any:
        # Mismo motivo que _get_bucket: google.cloud.storage.Client sin stubs.
        if self._client is not None:
            return self._client

        try:
            from google.cloud import storage
            from google.oauth2 import service_account
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is not installed") from exc

        client_kwargs = {}
        if self._config.project_id:
            client_kwargs["project"] = self._config.project_id
        if self._config.has_credentials_info():
            client_kwargs["credentials"] = service_account.Credentials.from_service_account_info(
                self._config.credentials_info
            )
        self._client = storage.Client(**client_kwargs)
        return self._client
