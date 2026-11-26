"""Infrastructure client for storage and remote file retrieval.

Este cliente encapsula operaciones tecnicas contra Google Cloud Storage y
descargas HTTP puntuales. No contiene reglas de negocio ni decisiones de API.
"""

import ipaddress
import logging
import mimetypes
import socket
import time
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.infrastructure.clients.storage_config import StorageConfig

logger = logging.getLogger(__name__)

# Default del SDK (~120s de retry deadline) es corto para archivos de
# decenas/cientos de MB: una escritura que se corta a medio camino
# (connection aborted / write timeout) agota ese presupuesto reintentando
# antes de completar, aunque la subida en si misma hubiera terminado bien
# con un poco mas de margen. Confirmado en produccion local (2026-09-07):
# el mismo pipeline via frontend no falla ni con 130MB, pero el proceso
# automatico si -- la maquina bajo carga (varios servicios + IDEs locales)
# hace mas probable que se corte una escritura larga.
_UPLOAD_TIMEOUT_SECONDS = 300
_UPLOAD_RETRY_DEADLINE_SECONDS = 300.0


def _upload_retry() -> Any:
    # Import perezoso, mismo motivo que _get_client(): evita que este modulo
    # dependa duro de google-api-core solo para construir un Retry.
    from google.api_core.retry import Retry

    return Retry(deadline=_UPLOAD_RETRY_DEADLINE_SECONDS)


def _download_retry(deadline_seconds: float) -> Any:
    from google.api_core.retry import Retry

    return Retry(deadline=deadline_seconds)


def _keepalive_socket_options(
    idle_seconds: int, interval_seconds: int, probes: int
) -> list[tuple[int, int, int]]:
    """Opciones de socket con TCP keepalive (las constantes TCP_KEEP* son solo Linux)."""
    options = [
        (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
        (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
    ]
    for name, value in (
        ("TCP_KEEPIDLE", idle_seconds),
        ("TCP_KEEPINTVL", interval_seconds),
        ("TCP_KEEPCNT", probes),
    ):
        if hasattr(socket, name):
            options.append((socket.IPPROTO_TCP, getattr(socket, name), value))
    return options


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
        content, _ = self.download_with_metadata(filename, bucket_name)
        return content

    def download_with_metadata(
        self,
        filename: str,
        bucket_name: str | None = None,
    ) -> tuple[bytes, str | None]:
        """Descarga un archivo desde GCS junto con su content type.

        ``get_blob`` consulta existencia y metadata en una sola llamada (antes eran
        exists + reload). Todas las llamadas llevan timeout y deadline de reintento
        acotados, y se loguea la duracion para detectar descargas lentas.
        """
        start = time.perf_counter()
        bucket = self._get_bucket(bucket_name)
        retry = _download_retry(self._config.download_retry_deadline)
        logger.info("downloading %s from bucket %s", filename, bucket.name)
        blob = bucket.get_blob(filename, timeout=self._config.download_timeout, retry=retry)
        if blob is None:
            raise FileNotFoundError(f"File {filename} not found in bucket {bucket.name}")

        content = blob.download_as_bytes(timeout=self._config.download_timeout, retry=retry)
        logger.info(
            "downloaded %s (%d bytes) from bucket %s in %.2fs",
            filename,
            len(content),
            bucket.name,
            time.perf_counter() - start,
        )
        return content, blob.content_type

    def resolve_bucket_name(self, bucket_name: str | None = None) -> str | None:
        """Bucket efectivo: el indicado o, si no viene, el por defecto configurado."""
        return bucket_name or self._config.default_bucket_name

    def delete_from_bucket(self, filename: str, bucket_name: str | None = None) -> bool:
        """Elimina un objeto de GCS. Retorna True si existia y se borro, False si ya no existia.

        Idempotente: un objeto inexistente (404) no es error, el llamador decide como tratarlo.
        Cualquier otra falla (red, permisos, 5xx) se propaga para que no se confunda con "no existia".
        """
        from google.api_core.exceptions import NotFound

        blob = self._get_bucket(bucket_name).blob(filename)
        try:
            blob.delete()
        except NotFound:
            logger.info("storage delete: %s not found in bucket %s", filename, blob.bucket.name)
            return False
        logger.info("storage delete: %s deleted from bucket %s", filename, blob.bucket.name)
        return True

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
        started = time.perf_counter()
        try:
            blob.upload_from_string(
                file_bytes,
                content_type=resolved_content_type or "application/octet-stream",
                timeout=_UPLOAD_TIMEOUT_SECONDS,
                retry=_upload_retry(),
            )
            logger.info(
                "gcs upload ok %s (%d bytes) in %.2fs",
                storage_name,
                len(file_bytes),
                time.perf_counter() - started,
            )
            return True
        except Exception as exc:  # noqa: BLE001 - operacion tecnica de GCS: la falla se convierte en success=False para el llamador
            logger.error(
                "storage upload failed for %s after %.2fs: %s",
                storage_name,
                time.perf_counter() - started,
                exc,
            )
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
            blob.upload_from_string(
                file_bytes,
                content_type=content_type,
                timeout=_UPLOAD_TIMEOUT_SECONDS,
                retry=_upload_retry(),
            )
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
            from google.cloud import storage  # type: ignore[attr-defined]
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
        client = storage.Client(**client_kwargs)
        self._enlarge_http_pool(client)
        self._client = client
        return client

    def _enlarge_http_pool(self, client: Any) -> None:
        """Amplia el pool de conexiones HTTP de GCS (urllib3 usa 10 por defecto).

        Las operaciones de storage corren en threads (asyncio.to_thread) y comparten un unico
        cliente; con mas de 10 concurrentes urllib3 descarta conexiones ("Connection pool is
        full, discarding connection") y debe re-abrir TLS cada vez.
        """
        from requests.adapters import HTTPAdapter

        size = self._config.http_pool_size
        socket_options = _keepalive_socket_options(
            self._config.tcp_keepalive_idle,
            self._config.tcp_keepalive_interval,
            self._config.tcp_keepalive_probes,
        )

        class _KeepAliveAdapter(HTTPAdapter):
            def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
                kwargs["socket_options"] = socket_options
                super().init_poolmanager(*args, **kwargs)

        # AuthorizedSession (client._http) es una requests.Session.
        adapter = _KeepAliveAdapter(pool_connections=size, pool_maxsize=size)
        client._http.mount("https://", adapter)
        client._http.mount("http://", adapter)
