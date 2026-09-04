"""Unit tests for StorageClient (GCS and httpx mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.clients.storage_client import StorageClient, _ensure_public_http_url


def make_config(
    *,
    default_bucket: str | None = "default-bucket",
    public_bucket: str | None = None,
    project_id: str | None = "test-project",
    credentials_info: dict | None = None,
) -> MagicMock:
    cfg = MagicMock()
    cfg.default_bucket_name = default_bucket
    cfg.public_bucket_name = public_bucket
    cfg.project_id = project_id
    cfg.credentials_info = credentials_info
    cfg.has_credentials_info.return_value = credentials_info is not None
    return cfg


# ---------------------------------------------------------------------------
# _ensure_public_http_url  (module-level SSRF guard)
# ---------------------------------------------------------------------------


class TestEnsurePublicHttpUrl:
    def test_non_http_scheme_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            _ensure_public_http_url("ftp://example.com/file.txt")

    def test_no_hostname_raises(self) -> None:
        with pytest.raises(ValueError, match="hostname"):
            _ensure_public_http_url("http:///path/only")

    def test_private_ip_raises(self) -> None:
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [(None, None, None, None, ("192.168.1.1", 0))]
            with pytest.raises(ValueError, match="private/internal"):
                _ensure_public_http_url("http://internal.host/file")

    def test_loopback_raises(self) -> None:
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [(None, None, None, None, ("127.0.0.1", 0))]
            with pytest.raises(ValueError, match="private/internal"):
                _ensure_public_http_url("http://localhost/file")

    def test_valid_public_url_does_not_raise(self) -> None:
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [(None, None, None, None, ("93.184.216.34", 0))]
            _ensure_public_http_url("http://example.com/file.txt")  # must not raise

    def test_hostname_resolving_to_private_ip_raises(self) -> None:
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [(None, None, None, None, ("10.0.0.1", 0))]
            with pytest.raises(ValueError, match="private/internal"):
                _ensure_public_http_url("http://internal.service.local/data")


# ---------------------------------------------------------------------------
# download_from_bucket
# ---------------------------------------------------------------------------


class TestDownloadFromBucket:
    def _make_client_with_blob(self, *, exists: bool, content: bytes = b"data") -> StorageClient:
        cfg = make_config()
        client = StorageClient(cfg)
        mock_blob = MagicMock()
        mock_blob.exists.return_value = exists
        mock_blob.download_as_bytes.return_value = content
        mock_blob.bucket.name = "default-bucket"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs = MagicMock()
        mock_gcs.bucket.return_value = mock_bucket
        client._client = mock_gcs
        return client

    def test_blob_exists_returns_bytes(self) -> None:
        client = self._make_client_with_blob(exists=True, content=b"hello")
        result = client.download_from_bucket("file.txt")
        assert result == b"hello"

    def test_blob_not_found_raises_file_not_found(self) -> None:
        client = self._make_client_with_blob(exists=False)
        with pytest.raises(FileNotFoundError):
            client.download_from_bucket("missing.txt")


# ---------------------------------------------------------------------------
# download_with_metadata
# ---------------------------------------------------------------------------


class TestDownloadWithMetadata:
    def test_returns_bytes_and_content_type(self) -> None:
        cfg = make_config()
        client = StorageClient(cfg)
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = b"content"
        mock_blob.content_type = "application/pdf"
        mock_blob.bucket.name = "default-bucket"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs = MagicMock()
        mock_gcs.bucket.return_value = mock_bucket
        client._client = mock_gcs

        data, ct = client.download_with_metadata("file.pdf")
        assert data == b"content"
        assert ct == "application/pdf"


# ---------------------------------------------------------------------------
# upload_bytes
# ---------------------------------------------------------------------------


class TestUploadBytes:
    def _make_upload_client(self) -> StorageClient:
        cfg = make_config()
        client = StorageClient(cfg)
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs = MagicMock()
        mock_gcs.bucket.return_value = mock_bucket
        client._client = mock_gcs
        return client

    def test_success_returns_true(self) -> None:
        client = self._make_upload_client()
        result = client.upload_bytes(b"data", "file.txt", "text/plain", "stored.txt")
        assert result is True

    def test_exception_logs_and_returns_false(self) -> None:
        client = self._make_upload_client()
        # Force the underlying blob.upload_from_string to raise
        gcs = client._client
        gcs.bucket.return_value.blob.return_value.upload_from_string.side_effect = RuntimeError(
            "gcs error"
        )
        result = client.upload_bytes(b"data", "file.txt", None, "stored.txt")
        assert result is False


# ---------------------------------------------------------------------------
# upload_public_bytes
# ---------------------------------------------------------------------------


class TestUploadPublicBytes:
    def test_no_public_bucket_returns_false_none(self) -> None:
        cfg = make_config(public_bucket=None)
        client = StorageClient(cfg)
        success, url = client.upload_public_bytes(b"data", "image/png")
        assert success is False
        assert url is None

    def test_success_returns_true_and_public_url(self) -> None:
        cfg = make_config(public_bucket="pub-bucket")
        client = StorageClient(cfg)
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs = MagicMock()
        mock_gcs.bucket.return_value = mock_bucket
        client._client = mock_gcs

        success, url = client.upload_public_bytes(b"img", "image/png")
        assert success is True
        assert url is not None
        assert url.startswith("https://storage.googleapis.com/pub-bucket/")


# ---------------------------------------------------------------------------
# download_from_url
# ---------------------------------------------------------------------------


class TestDownloadFromUrl:
    def test_valid_public_url_returns_bytes(self) -> None:
        cfg = make_config()
        client = StorageClient(cfg)
        mock_response = MagicMock()
        mock_response.content = b"remote data"
        mock_response.raise_for_status = MagicMock()

        with patch("socket.getaddrinfo") as mock_gai, patch("httpx.get") as mock_get:
            mock_gai.return_value = [(None, None, None, None, ("93.184.216.34", 0))]
            mock_get.return_value = mock_response
            result = client.download_from_url("http://example.com/file")

        assert result == b"remote data"

    def test_ssrf_blocked_url_raises_value_error(self) -> None:
        cfg = make_config()
        client = StorageClient(cfg)
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [(None, None, None, None, ("192.168.1.100", 0))]
            with pytest.raises(ValueError, match="private/internal"):
                client.download_from_url("http://internal.host/secret")


# ---------------------------------------------------------------------------
# _resolve_content_type
# ---------------------------------------------------------------------------


class TestResolveContentType:
    def setup_method(self) -> None:
        self.client = StorageClient(make_config())

    def test_explicit_content_type_used_as_is(self) -> None:
        ct = self.client._resolve_content_type("file.txt", "stored.txt", "application/pdf")
        assert ct == "application/pdf"

    def test_fallback_to_mimetypes_guess_type(self) -> None:
        ct = self.client._resolve_content_type("document.pdf", "stored", None)
        assert ct == "application/pdf"

    def test_whitespace_only_type_falls_back(self) -> None:
        ct = self.client._resolve_content_type("image.png", "stored", "  ")
        assert ct == "image/png"


# ---------------------------------------------------------------------------
# startup_event
# ---------------------------------------------------------------------------


class TestStartupEvent:
    def test_no_default_bucket_skips_gcs_check(self) -> None:
        cfg = make_config(default_bucket=None)
        client = StorageClient(cfg)
        # Must not call _get_client at all — no exception raised
        client.startup_event()

    def test_exception_in_gcs_is_caught_and_not_raised(self) -> None:
        cfg = make_config(default_bucket="my-bucket")
        client = StorageClient(cfg)
        # Force _get_client to raise; startup_event must swallow it
        with patch.object(client, "_get_bucket", side_effect=RuntimeError("gcs down")):
            client.startup_event()  # must not propagate
