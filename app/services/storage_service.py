"""Application service for storage-compatible endpoints.

Este modulo replica el comportamiento publico de los endpoints de storage del
micro Java limitandose a la superficie expuesta por ``StorageController``.
"""

import logging
from base64 import b64encode
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.infrastructure.clients.storage_client import StorageClient
from app.infrastructure.clients.storage_config import StorageConfig
from app.schemas.storage import FileResponse, UploadFileResponse, UploadPublicFileResponse

logger = logging.getLogger(__name__)


class StorageService:
    """Service de aplicacion para operaciones HTTP de storage."""

    _index_dir_name = "index"
    _metadata_file_name = "metadata.properties"
    _upload_id_suffix = ".upload"
    _private_dir_mode = 0o700

    def __init__(self, config: StorageConfig, storage_client: StorageClient) -> None:
        self._config = config
        self._storage_client = storage_client

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
        code_type_document: str | None,
        upload_content_bucket: bool | None,
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

        # PENDIENTE_INTEGRACION storage-upload-vectorization: se omite la
        # continuacion Java que envia documentos vectorizables a servicios de
        # documentos/vector store.
        # Dependencias faltantes: ParameterCommonService, VectorStoreService,
        # DocumentCommonService y persistencia de documentos/proyectos.
        # Impacto: el upload conserva la API publica pero no ejecuta efectos
        # laterales de vectorizacion ni actualizacion de estado documental.
        # Integracion futura: despues de un upload exitoso, replicar la logica
        # condicional de StorageManager.validateAndSendToSaveDocsOnVecstore.
        # Configuracion detectada en Java: bucket por defecto, projectId,
        # codeTypeDocument y parametros de chunk/overlap para vectorizacion.
        _ = project_id, code_type_document, upload_content_bucket

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
    ) -> None:
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

        # PENDIENTE_INTEGRACION storage-chunk-consolidation: en Java la
        # consolidacion posterior depende de DocumentDTO, validacion de
        # projectId, merge incremental de partes, upload final a GCS y limpieza
        # post-commit transaccional.
        # Dependencias faltantes: flujo de documentos persistidos y punto que
        # invoca consolidatePendingUploads desde el micro Java.
        # Impacto: este endpoint conserva el comportamiento observable de recibir
        # y persistir chunks, pero no cierra todavia el circuito indirecto de
        # ensamblado y publicacion del archivo consolidado.

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
