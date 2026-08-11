"""Application service for storage-compatible endpoints.

Este modulo replica el comportamiento publico de los endpoints de storage del
micro Java limitandose a la superficie expuesta por ``StorageController``, y
ademas dispara vectorizacion en background cuando corresponde (P-10, P-11 en
pendientes.md) -- integracion equivalente a
``StorageManager.validateAndSendToSaveDocsOnVecstore`` del micro Java origen.
"""

import asyncio
import base64
import logging
from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, HTTPException, UploadFile, status

from app.core.config import Settings
from app.infrastructure.clients.storage_client import StorageClient
from app.infrastructure.clients.storage_config import StorageConfig
from app.schemas.storage import (
    ChunkUploadResponse,
    FileResponse,
    UploadFileResponse,
    UploadPublicFileResponse,
)
from app.services.embedding.document_embedding_service import DocumentEmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class VectorizationTrigger:
    """Datos opcionales para disparar vectorizacion en background tras un
    upload exitoso (P-10/P-11 en pendientes.md). Agrupados en un solo objeto
    para no inflar la firma de ``upload_file``/``store_chunk`` con parametros
    sueltos (regla S107 de Sonar: maximo 13 parametros por metodo).

    ``code_type_document`` vive aqui y no como parametro suelto de upload
    porque, igual que en el micro Java origen, la subida cruda a storage no
    lo usa para nada -- solo importa para la decision/metadata de
    vectorizacion.
    """

    code_type_document: str | None = None
    upload_content_bucket: bool | None = None
    unique_code: str | None = None
    id_document: str | None = None
    background_tasks: BackgroundTasks | None = None


class StorageService:
    """Service de aplicacion para operaciones HTTP de storage."""

    _index_dir_name = "index"
    _metadata_file_name = "metadata.properties"
    _upload_id_suffix = ".upload"
    _private_dir_mode = 0o700

    def __init__(
        self,
        config: StorageConfig,
        storage_client: StorageClient,
        document_embedding_service: DocumentEmbeddingService,
        settings: Settings,
    ) -> None:
        self._config = config
        self._storage_client = storage_client
        self._document_embedding_service = document_embedding_service
        self._settings = settings

    @classmethod
    def _ensure_private_dir(cls, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True, mode=cls._private_dir_mode)
        path.chmod(cls._private_dir_mode)

    async def upload_file(
        self,
        file: UploadFile,
        name: str,
        bucket: str | None,
        project_id: str | None,
        vectorization: VectorizationTrigger | None = None,
    ) -> UploadFileResponse:
        try:
            file_bytes = await file.read()
        except Exception:
            logger.exception("failed to read uploaded file %r for storage upload", file.filename)
            return UploadFileResponse(success=False)

        success = self._storage_client.upload_bytes(
            file_bytes=file_bytes,
            file_name=file.filename,
            content_type=file.content_type,
            storage_name=name,
            bucket_name=bucket,
        )

        # P-10 (pendientes.md): equivalente a
        # StorageManager.validateAndSendToSaveDocsOnVecstore del micro Java
        # origen. Ahi el trigger real es "codeTypeDocument pertenece a una
        # lista configurable de tipos vectorizables" (una regla de negocio
        # que vive en la BD de Java, fuera del alcance de este servicio).
        # Aqui el trigger es explicito: uploadContentBucket=true + unique_code
        # presente -- mas simple y sin depender de estado que este servicio no
        # posee.
        trigger = vectorization or VectorizationTrigger()
        if (
            success
            and trigger.upload_content_bucket
            and trigger.unique_code
            and trigger.background_tasks is not None
        ):
            index_name = self._resolve_vectorization_index(project_id, trigger.code_type_document)
            trigger.background_tasks.add_task(
                self._vectorize_uploaded_file,
                file_bytes=file_bytes,
                file_name=file.filename or name,
                unique_code=trigger.unique_code,
                id_document=trigger.id_document or trigger.unique_code,
                index_name=index_name,
                code_type_document=trigger.code_type_document,
                bucket=bucket,
            )

        return UploadFileResponse(success=success)

    async def store_chunk(
        self,
        file: UploadFile,
        upload_id: str,
        chunk_index: int,
        total_chunks: int,
        file_name: str,
        name: str,
        bucket: str,
        id_area: str | None,
        project_id: str,
        vectorization: VectorizationTrigger | None = None,
    ) -> ChunkUploadResponse:
        root_path = Path(self._config.chunk_upload_temp_dir)
        upload_dir = root_path / upload_id
        index_dir = root_path / self._index_dir_name

        self._ensure_private_dir(root_path)
        self._ensure_private_dir(upload_dir)
        self._ensure_private_dir(index_dir)

        chunk_path = upload_dir / f"{chunk_index}.part"
        with chunk_path.open("wb") as chunk_file:
            chunk_file.write(await file.read())

        metadata_path = upload_dir / self._metadata_file_name
        metadata_lines = [
            f"fileName={file_name}",
            f"name={name}",
            f"bucket={bucket}",
            f"idArea={id_area or ''}",
            f"projectId={project_id}",
            f"totalChunks={total_chunks}",
        ]
        metadata_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")

        index_path = index_dir / f"{name}{self._upload_id_suffix}"
        index_path.write_text(upload_id, encoding="utf-8")

        # P-11 (pendientes.md): consolidacion automatica al recibir la ultima
        # parte, en la misma request (el merge en disco es rapido; a
        # diferencia de la vectorizacion, no hace falta background aqui).
        part_files = self._collect_ordered_parts(upload_dir)
        if len(part_files) < total_chunks:
            return ChunkUploadResponse(consolidated=False, success=True)

        success, file_bytes = self._consolidate_chunks(
            upload_dir=upload_dir,
            index_dir=index_dir,
            part_files=part_files,
            name=name,
            bucket=bucket,
            file_name=file_name,
        )

        trigger = vectorization or VectorizationTrigger()
        if (
            success
            and trigger.upload_content_bucket
            and trigger.unique_code
            and trigger.background_tasks is not None
        ):
            index_name = self._resolve_vectorization_index(project_id, trigger.code_type_document)
            trigger.background_tasks.add_task(
                self._vectorize_uploaded_file,
                file_bytes=file_bytes,
                file_name=file_name,
                unique_code=trigger.unique_code,
                id_document=trigger.id_document or trigger.unique_code,
                index_name=index_name,
                code_type_document=trigger.code_type_document,
                bucket=bucket,
            )

        return ChunkUploadResponse(consolidated=True, success=success)

    async def get_file(self, name: str, bucket: str | None) -> tuple[bytes, str | None]:
        try:
            return self._storage_client.download_with_metadata(
                filename=name,
                bucket_name=bucket,
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error getting file",
            ) from exc

    async def get_file_byte(self, name: str, bucket: str | None) -> FileResponse:
        file_bytes, content_type = await self.get_file(name=name, bucket=bucket)
        return FileResponse(
            application=content_type,
            base64=b64encode(file_bytes).decode("utf-8"),
        )

    async def upload_public_file(
        self,
        file: UploadFile,
        name: str,
        bucket: str | None,
        project_id: str | None,
        code_type_document: str | None,
        upload_content_bucket: bool | None,
    ) -> UploadPublicFileResponse:
        try:
            file_bytes = await file.read()
        except Exception:
            logger.exception(
                "failed to read uploaded file %r for public storage upload", file.filename
            )
            return UploadPublicFileResponse(success=False, url=None)

        success, url = self._storage_client.upload_public_bytes(
            file_bytes=file_bytes,
            content_type=file.content_type,
        )
        _ = name, bucket, project_id, code_type_document, upload_content_bucket
        return UploadPublicFileResponse(success=success, url=url)

    def _resolve_vectorization_index(
        self, project_id: str | None, code_type_document: str | None
    ) -> str:
        """Resuelve la coleccion vectorial destino.

        Sigue la convencion real del micro Java origen (confirmada leyendo
        ``StorageManager``/``VectorStoreMapper``): la coleccion es
        ``project-{projectId}``, una por proyecto. ``codeTypeDocument`` viaja
        como metadata, no como nombre de coleccion. Si no llega ``projectId``
        (campo opcional en este servicio), cae a ``codeTypeDocument`` y luego
        al default global.
        """
        if project_id:
            return f"project-{project_id}"
        if code_type_document:
            return code_type_document
        return self._settings.rag_default_collection_name

    async def _vectorize_uploaded_file(
        self,
        file_bytes: bytes,
        file_name: str,
        unique_code: str,
        id_document: str,
        index_name: str,
        code_type_document: str | None,
        bucket: str | None,
    ) -> None:
        """Vectoriza en background un archivo ya subido a storage.

        Corre como ``BackgroundTask``: la respuesta HTTP del upload ya se
        envio antes de que esto empiece (best-effort, sin callback -- ver
        integracion-java-storage.md seccion 2: el caller real, el micro Java,
        ya resuelve su propio estado con la respuesta sincrona de
        ``/embedding/save_document_vecstore``, no necesita que este servicio
        le avise de vuelta). El computo de embeddings es CPU-bound, por eso
        se corre en un thread aparte (``asyncio.to_thread``) para no bloquear
        el event loop mientras corre.
        """
        list_parameters: list[dict[str, Any]] = (
            [{"key": "code_type_document", "value": code_type_document}]
            if code_type_document
            else []
        )
        try:
            result = await asyncio.to_thread(
                self._document_embedding_service.save_document_to_vecstore,
                file_name=file_name,
                base64_content=base64.b64encode(file_bytes).decode("utf-8"),
                id_document=id_document,
                index_name=index_name,
                unique_code=unique_code,
                has_document_base64=True,
                bucket=bucket,
                list_parameters=list_parameters,
            )
            logger.info(
                "background vectorization finished for unique_code=%s index=%s success=%s",
                unique_code,
                index_name,
                result.get("success"),
            )
        except Exception:
            logger.exception(
                "background vectorization failed for unique_code=%s index=%s",
                unique_code,
                index_name,
            )

    @staticmethod
    def _collect_ordered_parts(upload_dir: Path) -> list[Path]:
        return sorted(upload_dir.glob("*.part"), key=lambda part: int(part.stem))

    def _consolidate_chunks(
        self,
        upload_dir: Path,
        index_dir: Path,
        part_files: list[Path],
        name: str,
        bucket: str,
        file_name: str,
    ) -> tuple[bool, bytes]:
        """Arma el archivo final a partir de las partes recibidas, lo sube y limpia."""
        merged = bytearray()
        for part in part_files:
            merged.extend(part.read_bytes())
        file_bytes = bytes(merged)

        success = self._storage_client.upload_bytes(
            file_bytes=file_bytes,
            file_name=file_name,
            content_type=None,
            storage_name=name,
            bucket_name=bucket,
        )
        self._cleanup_upload(upload_dir, part_files, index_dir, name)
        return success, file_bytes

    def _cleanup_upload(
        self,
        upload_dir: Path,
        part_files: list[Path],
        index_dir: Path,
        name: str,
    ) -> None:
        """Limpieza best-effort: no debe tumbar una consolidacion ya exitosa.

        Limitacion conocida (ver pendientes.md P-11): si el ultimo chunk se
        reintenta despues de esta limpieza, queda un directorio residual con
        1 ``.part`` huerfano -- no rompe nada, no se autolimpia solo.
        """
        try:
            for part in part_files:
                part.unlink(missing_ok=True)
            (upload_dir / self._metadata_file_name).unlink(missing_ok=True)
            upload_dir.rmdir()
            (index_dir / f"{name}{self._upload_id_suffix}").unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "failed to clean up chunk upload dir %s after consolidation", upload_dir
            )
