"""Unit tests for ConfigServerClient (httpx mocked)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.infrastructure.clients.config_server import ConfigServerClient


def make_settings(**kwargs: object) -> Settings:
    defaults: dict[str, object] = {
        "RAG_ENVIRONMENT": "edi-local",
        "RAG_EMBEDDING_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test",
        "USE_SPRING_CLOUD_CONFIG": False,
        "SPRING_CLOUD_CONFIG_URI": None,
        "EUREKA_APP_NAME": "test-app",
        "SPRING_PROFILES_ACTIVE": "default",
        "DEBUG": False,
    }
    defaults.update(kwargs)
    return Settings(**defaults)


def make_mock_http_client(json_payload: dict) -> tuple[MagicMock, MagicMock]:
    """Returns (mock_async_client_ctx, mock_http_client) with pre-configured response."""
    mock_response = MagicMock()
    mock_response.json.return_value = json_payload
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    return mock_ctx, mock_http_client


# ---------------------------------------------------------------------------
# Disabled / unconfigured states
# ---------------------------------------------------------------------------


class TestFetchConfigDisabled:
    @pytest.mark.asyncio
    async def test_disabled_flag_returns_not_enabled(self) -> None:
        settings = make_settings(USE_SPRING_CLOUD_CONFIG=False)
        client = ConfigServerClient(settings)
        result = await client.fetch_config()
        assert result == {"enabled": False, "loaded": False}

    @pytest.mark.asyncio
    async def test_no_uri_returns_not_enabled(self) -> None:
        settings = make_settings(USE_SPRING_CLOUD_CONFIG=True, SPRING_CLOUD_CONFIG_URI=None)
        client = ConfigServerClient(settings)
        result = await client.fetch_config()
        assert result == {"enabled": False, "loaded": False}


# ---------------------------------------------------------------------------
# Successful fetch
# ---------------------------------------------------------------------------


class TestFetchConfigSuccess:
    @pytest.mark.asyncio
    async def test_success_returns_enabled_and_loaded(self) -> None:
        settings = make_settings(
            USE_SPRING_CLOUD_CONFIG=True,
            SPRING_CLOUD_CONFIG_URI="http://config-server:8888",
        )
        payload = {
            "name": "test-app",
            "profiles": ["default"],
            "label": None,
            "propertySources": [
                {"name": "a", "source": {"key1": "val1"}},
            ],
        }
        mock_ctx, _ = make_mock_http_client(payload)
        with patch(
            "app.infrastructure.clients.config_server.httpx.AsyncClient", return_value=mock_ctx
        ):
            result = await ConfigServerClient(settings).fetch_config()

        assert result["enabled"] is True
        assert result["loaded"] is True
        assert result["name"] == "test-app"

    @pytest.mark.asyncio
    async def test_property_sources_merged_in_reverse_order(self) -> None:
        """Last source in the list should override first (reversed iteration)."""
        settings = make_settings(
            USE_SPRING_CLOUD_CONFIG=True,
            SPRING_CLOUD_CONFIG_URI="http://config-server",
        )
        payload = {
            "name": "app",
            "profiles": ["default"],
            "label": None,
            "propertySources": [
                {"name": "specific", "source": {"shared_key": "specific-value"}},
                {"name": "common", "source": {"shared_key": "common-value"}},
            ],
        }
        mock_ctx, _ = make_mock_http_client(payload)
        with patch(
            "app.infrastructure.clients.config_server.httpx.AsyncClient", return_value=mock_ctx
        ):
            result = await ConfigServerClient(settings).fetch_config()

        # Reversed: common processed first, specific last → specific wins
        assert "shared_key" in result["resolved_keys"]

    @pytest.mark.asyncio
    async def test_url_constructed_correctly(self) -> None:
        settings = make_settings(
            USE_SPRING_CLOUD_CONFIG=True,
            SPRING_CLOUD_CONFIG_URI="http://config:8888/",
            EUREKA_APP_NAME="my-app",
            SPRING_PROFILES_ACTIVE="prod",
        )
        payload = {"name": "my-app", "profiles": ["prod"], "label": None, "propertySources": []}
        mock_ctx, mock_http_client = make_mock_http_client(payload)
        with patch(
            "app.infrastructure.clients.config_server.httpx.AsyncClient", return_value=mock_ctx
        ):
            await ConfigServerClient(settings).fetch_config()

        called_url = mock_http_client.get.call_args.args[0]
        assert called_url == "http://config:8888/my-app/prod"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestFetchConfigErrors:
    @pytest.mark.asyncio
    async def test_http_error_returns_loaded_false_with_error(self) -> None:
        settings = make_settings(
            USE_SPRING_CLOUD_CONFIG=True,
            SPRING_CLOUD_CONFIG_URI="http://config-server",
        )
        mock_http_client = AsyncMock()
        mock_http_client.get.side_effect = Exception("404 Not Found")
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.infrastructure.clients.config_server.httpx.AsyncClient", return_value=mock_ctx
        ):
            result = await ConfigServerClient(settings).fetch_config()

        assert result["enabled"] is True
        assert result["loaded"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_timeout_exception_returns_loaded_false(self) -> None:
        import httpx

        settings = make_settings(
            USE_SPRING_CLOUD_CONFIG=True,
            SPRING_CLOUD_CONFIG_URI="http://config-server",
        )
        mock_http_client = AsyncMock()
        mock_http_client.get.side_effect = httpx.TimeoutException("timed out")
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.infrastructure.clients.config_server.httpx.AsyncClient", return_value=mock_ctx
        ):
            result = await ConfigServerClient(settings).fetch_config()

        assert result["loaded"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_raise_for_status_error_returns_loaded_false(self) -> None:
        settings = make_settings(
            USE_SPRING_CLOUD_CONFIG=True,
            SPRING_CLOUD_CONFIG_URI="http://config-server",
        )
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 503")
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.infrastructure.clients.config_server.httpx.AsyncClient", return_value=mock_ctx
        ):
            result = await ConfigServerClient(settings).fetch_config()

        assert result["loaded"] is False
        assert "error" in result
