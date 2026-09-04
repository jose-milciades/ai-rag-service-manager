"""Tests for app/main.py — create_app(), CORS configuration, and root endpoint."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STARTUP_PATCHES = (
    "app.infrastructure.clients.config_server.ConfigServerClient.fetch_config",
    "app.infrastructure.clients.eureka.EurekaRegistrar.register",
    "app.infrastructure.clients.eureka.EurekaRegistrar.stop",
)


def _make_app(settings: Settings) -> FastAPI:
    """Create a fresh FastAPI app with all external integrations patched out."""
    with (
        patch("app.main.get_settings", return_value=settings),
        patch(
            _STARTUP_PATCHES[0],
            new_callable=AsyncMock,
            return_value={"enabled": False, "loaded": False},
        ),
        patch(
            _STARTUP_PATCHES[1],
            new_callable=AsyncMock,
            return_value={"enabled": False, "registered": False},
        ),
        patch(_STARTUP_PATCHES[2], new_callable=AsyncMock, return_value=None),
        patch(
            "app.infrastructure.clients.storage_client.StorageClient.startup_event",
            new=Mock(),
        ),
    ):
        from app.main import create_app  # deferred — patches must be active first

        return create_app()


# ---------------------------------------------------------------------------
# create_app() — title
# ---------------------------------------------------------------------------


def test_create_app_title_matches_settings(test_app: FastAPI, mock_settings: Settings) -> None:
    """create_app() sets FastAPI title to settings.app_name."""
    assert test_app.title == mock_settings.app_name


# ---------------------------------------------------------------------------
# CORS — wildcard origins
# ---------------------------------------------------------------------------


def test_cors_wildcard_allow_all_origins(test_app: FastAPI) -> None:
    """Default settings use '*', so Access-Control-Allow-Origin is '*'."""
    client = TestClient(test_app)
    response = client.get("/", headers={"Origin": "http://example.com"})
    assert response.headers.get("Access-Control-Allow-Origin") == "*"


def test_cors_wildcard_no_credentials(test_app: FastAPI) -> None:
    """With wildcard origins, allow_credentials is False — header must not be 'true'."""
    client = TestClient(test_app)
    response = client.get("/", headers={"Origin": "http://example.com"})
    creds = response.headers.get("Access-Control-Allow-Credentials", "false")
    assert creds != "true"


# ---------------------------------------------------------------------------
# CORS — explicit origins
# ---------------------------------------------------------------------------


def test_cors_explicit_origins_returns_matched_origin(mock_settings: Settings) -> None:
    """Explicit CORS origins: matching Origin header is echoed back."""
    mock_settings.cors_allowed_origins = "http://localhost:3000,http://app.example.com"
    app = _make_app(mock_settings)
    client = TestClient(app)
    response = client.get("/", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"


def test_cors_explicit_origins_allow_credentials(mock_settings: Settings) -> None:
    """Explicit CORS origins: allow_credentials is True for a matching Origin."""
    mock_settings.cors_allowed_origins = "http://localhost:3000"
    app = _make_app(mock_settings)
    client = TestClient(app)
    response = client.get("/", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("Access-Control-Allow-Credentials") == "true"


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------


def test_root_endpoint_status_and_fields(test_client: TestClient) -> None:
    """GET / returns 200 with all expected keys."""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "environment" in data
    assert "api_prefix" in data
    assert "docs" in data


@pytest.mark.parametrize("field,expected", [("docs", "/docs")])
def test_root_endpoint_docs_value(test_client: TestClient, field: str, expected: str) -> None:
    """Root endpoint docs field is always '/docs'."""
    response = test_client.get("/")
    assert response.json()[field] == expected
