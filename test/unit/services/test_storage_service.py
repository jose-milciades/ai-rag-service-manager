"""Unit tests for app.services.storage_service."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import BackgroundTasks, UploadFile

from app.core.config import Settings
from app.schemas.storage import (
    ChunkUploadResponse,
    FileResponse,
    UploadFileResponse,
    UploadPublicFileResponse,
)
from app.services.storage_service import StorageService, VectorizationTrigger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_upload_file(
    content: bytes = b"test file content",
    filename: str = "test.txt",
    content_type: str = "text/plain",
) -> Mock:
    """Create a Mock UploadFile whose .read() coroutine returns content."""
    mock_file = Mock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=content)
    mock_file.filename = filename
    mock_file.content_type = content_type
    return mock_file


def _make_mock_upload_file_raises(exc: Exception, filename: str = "test.txt") -> Mock:
    mock_file = Mock(spec=UploadFile)
    mock_file.read = AsyncMock(side_effect=exc)
    mock_file.filename = filename
    mock_file.content_type = "text/plain"
    return mock_file


def _make_service(
    settings: Settings,
    tmp_path: Path,
    storage_client: Mock | None = None,
    embedding_service: Mock | None = None,
) -> StorageService:
    if storage_client is None:
        storage_client = Mock()
        storage_client.upload_bytes.return_value = True
        storage_client.download_with_metadata.return_value = (b"bytes", "text/plain")
    if embedding_service is None:
        embedding_service = Mock()

    config = Mock()
    config.chunk_upload_temp_dir = str(tmp_path / "uploads")

    return StorageService(
        config=config,
        storage_client=storage_client,
        document_embedding_service=embedding_service,
        settings=settings,
    )


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------


class TestUploadFile:
    @pytest.mark.asyncio
    async def test_success_returns_upload_file_response_true(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        sc = Mock()
        sc.upload_bytes.return_value = True
        service = _make_service(mock_settings, tmp_path, storage_client=sc)
        mock_file = _make_mock_upload_file()

        response = await service.upload_file(
            file=mock_file, name="stored_name", bucket="my-bucket", project_id=None
        )
        assert isinstance(response, UploadFileResponse)
        assert response.success is True

    @pytest.mark.asyncio
    async def test_file_read_raises_returns_success_false(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        service = _make_service(mock_settings, tmp_path)
        mock_file = _make_mock_upload_file_raises(OSError("read error"))

        response = await service.upload_file(
            file=mock_file, name="stored_name", bucket="my-bucket", project_id=None
        )
        assert response.success is False

    @pytest.mark.asyncio
    async def test_vectorization_trigger_adds_task_when_all_conditions_met(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        sc = Mock()
        sc.upload_bytes.return_value = True
        emb = Mock()
        service = _make_service(mock_settings, tmp_path, storage_client=sc, embedding_service=emb)
        mock_file = _make_mock_upload_file()
        bg = Mock(spec=BackgroundTasks)

        trigger = VectorizationTrigger(
            upload_content_bucket=True,
            unique_code="uc1",
            background_tasks=bg,
        )
        await service.upload_file(
            file=mock_file,
            name="stored_name",
            bucket="my-bucket",
            project_id=None,
            vectorization=trigger,
        )
        bg.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_vectorization_not_triggered_when_missing_unique_code(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        sc = Mock()
        sc.upload_bytes.return_value = True
        service = _make_service(mock_settings, tmp_path, storage_client=sc)
        mock_file = _make_mock_upload_file()
        bg = Mock(spec=BackgroundTasks)

        trigger = VectorizationTrigger(
            upload_content_bucket=True,
            unique_code=None,  # missing
            background_tasks=bg,
        )
        await service.upload_file(
            file=mock_file, name="n", bucket=None, project_id=None, vectorization=trigger
        )
        bg.add_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_vectorization_not_triggered_when_missing_background_tasks(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        sc = Mock()
        sc.upload_bytes.return_value = True
        service = _make_service(mock_settings, tmp_path, storage_client=sc)
        mock_file = _make_mock_upload_file()

        trigger = VectorizationTrigger(
            upload_content_bucket=True,
            unique_code="uc1",
            background_tasks=None,  # missing
        )
        await service.upload_file(
            file=mock_file, name="n", bucket=None, project_id=None, vectorization=trigger
        )
        # No background_tasks → no add_task called (would raise AttributeError if called)

    @pytest.mark.asyncio
    async def test_vectorization_not_triggered_when_upload_content_bucket_false(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        sc = Mock()
        sc.upload_bytes.return_value = True
        service = _make_service(mock_settings, tmp_path, storage_client=sc)
        mock_file = _make_mock_upload_file()
        bg = Mock(spec=BackgroundTasks)

        trigger = VectorizationTrigger(
            upload_content_bucket=False,
            unique_code="uc1",
            background_tasks=bg,
        )
        await service.upload_file(
            file=mock_file, name="n", bucket=None, project_id=None, vectorization=trigger
        )
        bg.add_task.assert_not_called()


# ---------------------------------------------------------------------------
# store_chunk
# ---------------------------------------------------------------------------


class TestStoreChunk:
    @pytest.mark.asyncio
    async def test_intermediate_chunk_returns_consolidated_false(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        service = _make_service(mock_settings, tmp_path)
        mock_file = _make_mock_upload_file(content=b"chunk data")

        response = await service.store_chunk(
            file=mock_file,
            upload_id="upload-1",
            chunk_index=0,
            total_chunks=3,  # 3 total, only 1 received
            file_name="bigfile.txt",
            name="bigfile",
            bucket=None,
            id_area=None,
            project_id="proj1",
        )
        assert isinstance(response, ChunkUploadResponse)
        assert response.consolidated is False
        assert response.success is True

    @pytest.mark.asyncio
    async def test_final_chunk_returns_consolidated_true(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        sc = Mock()
        sc.upload_bytes.return_value = True
        service = _make_service(mock_settings, tmp_path, storage_client=sc)

        # Upload chunk 0 and then chunk 1 (total=2 → consolidates on second)
        file0 = _make_mock_upload_file(content=b"part0", filename="bigfile.txt")
        file1 = _make_mock_upload_file(content=b"part1", filename="bigfile.txt")

        await service.store_chunk(
            file=file0,
            upload_id="upload-2",
            chunk_index=0,
            total_chunks=2,
            file_name="bigfile.txt",
            name="bigfile",
            bucket=None,
            id_area=None,
            project_id="proj1",
        )
        response = await service.store_chunk(
            file=file1,
            upload_id="upload-2",
            chunk_index=1,
            total_chunks=2,
            file_name="bigfile.txt",
            name="bigfile",
            bucket=None,
            id_area=None,
            project_id="proj1",
        )
        assert response.consolidated is True
        sc.upload_bytes.assert_called()

    @pytest.mark.asyncio
    async def test_final_chunk_with_vectorization_trigger_calls_add_task(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        sc = Mock()
        sc.upload_bytes.return_value = True
        service = _make_service(mock_settings, tmp_path, storage_client=sc)
        bg = Mock(spec=BackgroundTasks)

        file0 = _make_mock_upload_file(content=b"data", filename="f.txt")
        file1 = _make_mock_upload_file(content=b"more", filename="f.txt")

        trigger = VectorizationTrigger(
            upload_content_bucket=True,
            unique_code="uc1",
            background_tasks=bg,
        )
        await service.store_chunk(
            file=file0,
            upload_id="upload-3",
            chunk_index=0,
            total_chunks=2,
            file_name="f.txt",
            name="f",
            bucket=None,
            id_area=None,
            project_id="p1",
        )
        await service.store_chunk(
            file=file1,
            upload_id="upload-3",
            chunk_index=1,
            total_chunks=2,
            file_name="f.txt",
            name="f",
            bucket=None,
            id_area=None,
            project_id="p1",
            vectorization=trigger,
        )
        bg.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_directories(self, mock_settings: Settings, tmp_path: Path) -> None:
        service = _make_service(mock_settings, tmp_path)
        mock_file = _make_mock_upload_file()

        await service.store_chunk(
            file=mock_file,
            upload_id="upload-dir-test",
            chunk_index=0,
            total_chunks=10,
            file_name="f.txt",
            name="f",
            bucket=None,
            id_area=None,
            project_id="p1",
        )
        upload_dir = tmp_path / "uploads" / "upload-dir-test"
        assert upload_dir.exists()
        assert upload_dir.is_dir()

    @pytest.mark.asyncio
    async def test_writes_chunk_part_file(self, mock_settings: Settings, tmp_path: Path) -> None:
        service = _make_service(mock_settings, tmp_path)
        mock_file = _make_mock_upload_file(content=b"chunk bytes")

        await service.store_chunk(
            file=mock_file,
            upload_id="upload-part-test",
            chunk_index=2,
            total_chunks=10,
            file_name="f.txt",
            name="f",
            bucket=None,
            id_area=None,
            project_id="p1",
        )
        part_file = tmp_path / "uploads" / "upload-part-test" / "2.part"
        assert part_file.exists()
        assert part_file.read_bytes() == b"chunk bytes"

    @pytest.mark.asyncio
    async def test_writes_metadata_properties_file(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        service = _make_service(mock_settings, tmp_path)
        mock_file = _make_mock_upload_file()

        await service.store_chunk(
            file=mock_file,
            upload_id="upload-meta-test",
            chunk_index=0,
            total_chunks=5,
            file_name="myfile.txt",
            name="myname",
            bucket="my-bucket",
            id_area="area1",
            project_id="proj99",
        )
        meta_file = tmp_path / "uploads" / "upload-meta-test" / "metadata.properties"
        assert meta_file.exists()
        content = meta_file.read_text()
        assert "fileName=myfile.txt" in content
        assert "name=myname" in content
        assert "bucket=my-bucket" in content
        assert "projectId=proj99" in content


# ---------------------------------------------------------------------------
# get_file
# ---------------------------------------------------------------------------


class TestGetFile:
    @pytest.mark.asyncio
    async def test_download_succeeds_returns_bytes_and_content_type(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        sc = Mock()
        sc.download_with_metadata.return_value = (b"file bytes", "text/plain")
        service = _make_service(mock_settings, tmp_path, storage_client=sc)

        file_bytes, content_type = await service.get_file("myfile.txt", "bucket")
        assert file_bytes == b"file bytes"
        assert content_type == "text/plain"

    @pytest.mark.asyncio
    async def test_file_not_found_raises_http_404(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        from fastapi import HTTPException

        sc = Mock()
        sc.download_with_metadata.side_effect = FileNotFoundError("not found")
        service = _make_service(mock_settings, tmp_path, storage_client=sc)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_file("missing.txt", None)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_generic_exception_raises_http_500(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        from fastapi import HTTPException

        sc = Mock()
        sc.download_with_metadata.side_effect = RuntimeError("unexpected")
        service = _make_service(mock_settings, tmp_path, storage_client=sc)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_file("file.txt", None)
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# get_file_byte
# ---------------------------------------------------------------------------


class TestGetFileByte:
    @pytest.mark.asyncio
    async def test_returns_file_response_with_base64(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        import base64

        sc = Mock()
        sc.download_with_metadata.return_value = (b"hello", "text/plain")
        service = _make_service(mock_settings, tmp_path, storage_client=sc)

        response = await service.get_file_byte("f.txt", None)
        assert isinstance(response, FileResponse)
        assert response.base64 == base64.b64encode(b"hello").decode()
        assert response.application == "text/plain"


# ---------------------------------------------------------------------------
# upload_public_file
# ---------------------------------------------------------------------------


class TestUploadPublicFile:
    @pytest.mark.asyncio
    async def test_success_returns_true_and_url(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        sc = Mock()
        sc.upload_public_bytes.return_value = (True, "https://storage.example.com/uuid")
        service = _make_service(mock_settings, tmp_path, storage_client=sc)
        mock_file = _make_mock_upload_file()

        response = await service.upload_public_file(
            file=mock_file,
            name="pub",
            bucket=None,
            project_id=None,
            code_type_document=None,
            upload_content_bucket=None,
        )
        assert isinstance(response, UploadPublicFileResponse)
        assert response.success is True
        assert response.url == "https://storage.example.com/uuid"

    @pytest.mark.asyncio
    async def test_file_read_raises_returns_success_false(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        service = _make_service(mock_settings, tmp_path)
        mock_file = _make_mock_upload_file_raises(OSError("io error"))

        response = await service.upload_public_file(
            file=mock_file,
            name="pub",
            bucket=None,
            project_id=None,
            code_type_document=None,
            upload_content_bucket=None,
        )
        assert response.success is False
        assert response.url is None


# ---------------------------------------------------------------------------
# _resolve_vectorization_index
# ---------------------------------------------------------------------------


class TestResolveVectorizationIndex:
    def _svc(self, mock_settings: Settings, tmp_path: Path) -> StorageService:
        return _make_service(mock_settings, tmp_path)

    def test_project_id_returns_project_prefixed(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        svc = self._svc(mock_settings, tmp_path)
        result = svc._resolve_vectorization_index("42", None)
        assert result == "project-42"

    def test_no_project_id_uses_code_type_document(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        svc = self._svc(mock_settings, tmp_path)
        result = svc._resolve_vectorization_index(None, "contracts")
        assert result == "contracts"

    def test_neither_uses_default_collection_name(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        svc = self._svc(mock_settings, tmp_path)
        result = svc._resolve_vectorization_index(None, None)
        assert result == mock_settings.rag_default_collection_name


# ---------------------------------------------------------------------------
# _vectorize_uploaded_file
# ---------------------------------------------------------------------------


class TestVectorizeUploadedFile:
    @pytest.mark.asyncio
    async def test_encodes_to_base64_and_calls_save_document(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        import base64

        emb = Mock()
        emb.save_document_to_vecstore.return_value = {"success": True}
        service = _make_service(mock_settings, tmp_path, embedding_service=emb)

        file_bytes = b"pdf content"
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = {"success": True}
            await service._vectorize_uploaded_file(
                file_bytes=file_bytes,
                file_name="doc.pdf",
                unique_code="uc1",
                id_document="id1",
                index_name="idx",
                code_type_document=None,
                bucket=None,
            )
        mock_to_thread.assert_called_once()
        call_kwargs = mock_to_thread.call_args.kwargs
        assert call_kwargs["has_document_base64"] is True
        assert call_kwargs["base64_content"] == base64.b64encode(file_bytes).decode()

    @pytest.mark.asyncio
    async def test_exception_is_logged_not_raised(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        service = _make_service(mock_settings, tmp_path)

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = RuntimeError("embedding error")
            # Should NOT raise
            await service._vectorize_uploaded_file(
                file_bytes=b"data",
                file_name="f.txt",
                unique_code="uc1",
                id_document="id1",
                index_name="idx",
                code_type_document=None,
                bucket=None,
            )


# ---------------------------------------------------------------------------
# _collect_ordered_parts
# ---------------------------------------------------------------------------


class TestCollectOrderedParts:
    def test_returns_part_files_sorted_numerically(self, tmp_path: Path) -> None:
        upload_dir = tmp_path / "upload"
        upload_dir.mkdir()
        # Create out-of-order part files
        (upload_dir / "2.part").write_bytes(b"c")
        (upload_dir / "0.part").write_bytes(b"a")
        (upload_dir / "10.part").write_bytes(b"k")
        (upload_dir / "1.part").write_bytes(b"b")

        parts = StorageService._collect_ordered_parts(upload_dir)
        assert [p.stem for p in parts] == ["0", "1", "2", "10"]

    def test_empty_dir_returns_empty_list(self, tmp_path: Path) -> None:
        upload_dir = tmp_path / "empty"
        upload_dir.mkdir()
        assert StorageService._collect_ordered_parts(upload_dir) == []


# ---------------------------------------------------------------------------
# _consolidate_chunks
# ---------------------------------------------------------------------------


class TestConsolidateChunks:
    def test_concatenates_parts_and_calls_upload_bytes(
        self, mock_settings: Settings, tmp_path: Path
    ) -> None:
        sc = Mock()
        sc.upload_bytes.return_value = True
        service = _make_service(mock_settings, tmp_path, storage_client=sc)

        upload_dir = tmp_path / "uploads" / "upload-x"
        index_dir = tmp_path / "uploads" / "index"
        upload_dir.mkdir(parents=True)
        index_dir.mkdir(parents=True)

        (upload_dir / "0.part").write_bytes(b"hello ")
        (upload_dir / "1.part").write_bytes(b"world")
        part_files = StorageService._collect_ordered_parts(upload_dir)

        success, file_bytes = service._consolidate_chunks(
            upload_dir=upload_dir,
            index_dir=index_dir,
            part_files=part_files,
            name="merged_file",
            bucket=None,
            file_name="merged.txt",
        )
        assert success is True
        assert file_bytes == b"hello world"
        sc.upload_bytes.assert_called_once()
        args = sc.upload_bytes.call_args.kwargs
        assert args["file_bytes"] == b"hello world"
        assert args["file_name"] == "merged.txt"
