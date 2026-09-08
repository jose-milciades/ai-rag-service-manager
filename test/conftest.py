"""Shared pytest fixtures for the ai-rag-service-manager test suite."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.services import (
    get_document_embedding_service,
    get_embedding_provider,
    get_storage_client,
    get_storage_config,
    get_storage_service,
    get_vector_store_manager,
)
from app.core.config import Settings, get_settings
from app.infrastructure.vector_store.vector_store_manager import VectorStoreManager

# NOTE: app.main is NOT imported at module level because `app = create_app()` at
# module scope in app/main.py calls get_settings() immediately, which may fail
# if the test environment has unexpected env-var values.  We import create_app
# lazily inside the fixture body where the patches are already active.


# ---------------------------------------------------------------------------
# Settings / config
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_settings() -> Generator[Settings, None, None]:
    """Real Settings instance with safe test values; clears all lru_caches on teardown."""
    settings = Settings(
        RAG_ENVIRONMENT="edi-local",
        OPENAI_API_KEY="sk-test-key",
        VECTOR_DB_TYPE="memory",
        EUREKA_ENABLED=False,
        USE_SPRING_CLOUD_CONFIG=False,
        DEBUG=False,
        APP_ENV="test",
        EUREKA_APP_NAME="ai-rag-service-manager",
        APP_API_PREFIX="/api/v1",
        APP_PORT=8000,
        RAG_EMBEDDING_PROVIDER="openai",
        RAG_EMBEDDING_MODEL="text-embedding-3-small",
    )
    yield settings

    # Teardown: clear all lru_cache singletons so next test gets a fresh instance.
    get_settings.cache_clear()
    get_vector_store_manager.cache_clear()
    get_embedding_provider.cache_clear()
    get_storage_config.cache_clear()
    get_storage_client.cache_clear()
    get_document_embedding_service.cache_clear()
    get_storage_service.cache_clear()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_app(mock_settings: Settings) -> Generator[FastAPI, None, None]:
    """FastAPI application with all external-integration startup hooks mocked."""
    with (
        patch("app.core.config.get_settings", return_value=mock_settings),
        patch("app.main.get_settings", return_value=mock_settings),
        patch("app.api.routes.health_controller.get_settings", return_value=mock_settings),
        patch("app.schemas.embedding.get_settings", return_value=mock_settings),
        patch("app.api.dependencies.services.get_settings", return_value=mock_settings),
        patch(
            "app.infrastructure.clients.config_server.ConfigServerClient.fetch_config",
            new_callable=AsyncMock,
            return_value={"enabled": False, "loaded": False},
        ),
        patch(
            "app.infrastructure.clients.eureka.EurekaRegistrar.register",
            new_callable=AsyncMock,
            return_value={"enabled": False, "registered": False},
        ),
        patch(
            "app.infrastructure.clients.eureka.EurekaRegistrar.stop",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.infrastructure.clients.storage_client.StorageClient.startup_event",
            new=Mock(),
        ),
    ):
        # Deferred import: importing app.main at module level would run
        # `app = create_app()` before patches are active, causing failures
        # with unexpected env-var values in the test process.
        from app.main import create_app

        application = create_app()
        yield application
        application.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# HTTP test client
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_client(test_app: FastAPI) -> TestClient:
    """Synchronous TestClient wrapping the mocked FastAPI application."""
    return TestClient(test_app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Infrastructure mocks
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_embedding_provider() -> Mock:
    """Mock EmbeddingProvider with sensible defaults."""
    provider = Mock()
    provider.dim = 1536
    provider.model_name = "text-embedding-3-small"
    provider.embed_documents.return_value = [[0.1] * 1536]
    provider.embed_query.return_value = [0.1] * 1536
    return provider


@pytest.fixture()
def mock_vector_store_manager() -> Mock:
    """Mock VectorStoreManager (spec-based for attribute safety)."""
    return Mock(spec=VectorStoreManager)


@pytest.fixture()
def mock_storage_client() -> Mock:
    """Mock StorageClient with sensible defaults (no spec — complex init)."""
    client = Mock()
    client.upload_bytes.return_value = True
    client.download_from_bucket.return_value = b"test content"
    return client


@pytest.fixture()
def in_memory_vector_store_manager(mock_settings: Settings) -> VectorStoreManager:
    """Real VectorStoreManager backed by InMemoryVectorStore (no external deps)."""
    return VectorStoreManager(settings=mock_settings)


# ---------------------------------------------------------------------------
# Service mocks
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_document_embedding_service() -> Mock:
    """Mock DocumentEmbeddingService with method stubs matching real return shapes."""
    svc = Mock()
    svc.embed_document.return_value = {"status": "ok", "chunks": 1}
    svc.search_similar_documents.return_value = {"results": [], "total": 0}
    svc.delete_document_embeddings.return_value = {"deleted": 0}
    svc.list_document_embeddings.return_value = {"items": [], "total": 0}
    return svc


@pytest.fixture()
def mock_storage_service() -> Mock:
    """Mock StorageService with async stubs for all public methods."""
    svc = Mock()
    svc.upload_file = AsyncMock(return_value={"status": "ok"})
    svc.store_chunk = AsyncMock(return_value={"status": "ok"})
    svc.get_file = AsyncMock(return_value={"content": ""})
    svc.get_file_bytes = AsyncMock(return_value=b"")
    svc.upload_public_file = AsyncMock(return_value={"url": ""})
    return svc


def override_dependency(app: FastAPI, dependency: Any, mock: Any) -> None:
    """Helper: register a dependency override on a FastAPI app instance."""
    app.dependency_overrides[dependency] = lambda: mock
