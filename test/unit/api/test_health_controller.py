"""Unit tests for GET /health/live and GET /health/ready endpoints."""

from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings

# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------


def test_liveness_returns_200(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_liveness_method_not_allowed(test_client: TestClient) -> None:
    response = test_client.post("/api/v1/health/live")
    assert response.status_code == 405


# ---------------------------------------------------------------------------
# Correlation ID middleware
# ---------------------------------------------------------------------------


def test_correlation_id_propagated(test_client: TestClient) -> None:
    response = test_client.get(
        "/api/v1/health/live",
        headers={"X-Correlation-ID": "my-trace-id-123"},
    )
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == "my-trace-id-123"


def test_correlation_id_generated_when_absent(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/health/live")
    assert response.status_code == 200
    # The middleware should generate a correlation ID if none was provided.
    assert response.headers.get("X-Correlation-ID") is not None


# ---------------------------------------------------------------------------
# Readiness — all integrations disabled (default test_app state)
# ---------------------------------------------------------------------------


def test_readiness_all_disabled_returns_200(test_app: FastAPI) -> None:
    """Default test_app has both integrations disabled — should be ready."""
    test_app.state.remote_config = {"enabled": False, "loaded": False}
    test_app.state.eureka = {"enabled": False, "registered": False}
    client = TestClient(test_app)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["failed_dependencies"] == []
    assert body["blocking_failures"] == []


def test_readiness_contains_service_and_env(test_app: FastAPI, mock_settings: Settings) -> None:
    test_app.state.remote_config = {"enabled": False, "loaded": False}
    test_app.state.eureka = {"enabled": False, "registered": False}
    client = TestClient(test_app)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == mock_settings.app_name
    assert body["environment"] == mock_settings.app_env


# ---------------------------------------------------------------------------
# Readiness — critical dependency fails → 503
# ---------------------------------------------------------------------------


def test_readiness_critical_config_server_fails(test_app: FastAPI) -> None:
    """config_server enabled but not loaded and is in critical list → 503."""
    test_app.state.remote_config = {"enabled": True, "loaded": False}
    test_app.state.eureka = {"enabled": False, "registered": False}
    client = TestClient(test_app)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert "config_server" in body["blocking_failures"]
    assert "config_server" in body["failed_dependencies"]


def test_readiness_critical_eureka_fails(test_app: FastAPI) -> None:
    """eureka enabled but not registered and is in critical list → 503."""
    test_app.state.remote_config = {"enabled": False, "loaded": False}
    test_app.state.eureka = {"enabled": True, "registered": False}
    client = TestClient(test_app)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert "eureka" in body["blocking_failures"]


# ---------------------------------------------------------------------------
# Readiness — non-critical dependency fails → 200 but reported
# ---------------------------------------------------------------------------


def test_readiness_non_critical_dep_fails_still_200(
    test_app: FastAPI, mock_settings: Settings
) -> None:
    """A failing dependency not in READINESS_CRITICAL_DEPENDENCIES does not block."""
    # Use a minimal Mock so we don't construct a real Settings with env-var side effects.
    limited_settings = Mock()
    limited_settings.readiness_critical_dependencies = "eureka"
    limited_settings.app_name = mock_settings.app_name
    limited_settings.app_env = mock_settings.app_env

    with patch(
        "app.api.routes.health_controller.get_settings",
        return_value=limited_settings,
    ):
        test_app.state.remote_config = {"enabled": True, "loaded": False}
        test_app.state.eureka = {"enabled": False, "registered": False}
        client = TestClient(test_app)
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert "config_server" in body["failed_dependencies"]
    assert "config_server" not in body["blocking_failures"]


# ---------------------------------------------------------------------------
# Readiness — both integrations succeed
# ---------------------------------------------------------------------------


def test_readiness_both_integrations_ok(test_app: FastAPI) -> None:
    test_app.state.remote_config = {"enabled": True, "loaded": True}
    test_app.state.eureka = {"enabled": True, "registered": True}
    client = TestClient(test_app)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["failed_dependencies"] == []
    assert body["blocking_failures"] == []
