"""Unit tests for EurekaRegistrar (py_eureka_client mocked)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.infrastructure.clients.eureka import EurekaRegistrar


def make_settings(**kwargs: object) -> Settings:
    defaults: dict[str, object] = {
        "RAG_ENVIRONMENT": "edi-local",
        "RAG_EMBEDDING_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test",
        "EUREKA_ENABLED": True,
        "EUREKA_REGISTER_MAX_RETRIES": 3,
        "EUREKA_REGISTER_RETRY_DELAY": 0,
        "DEBUG": False,
    }
    defaults.update(kwargs)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# register() — disabled / missing client
# ---------------------------------------------------------------------------


class TestEurekaRegisterDisabled:
    @pytest.mark.asyncio
    async def test_disabled_returns_not_enabled(self) -> None:
        settings = make_settings(EUREKA_ENABLED=False)
        registrar = EurekaRegistrar(settings)
        result = await registrar.register()
        assert result == {"enabled": False, "registered": False}

    @pytest.mark.asyncio
    async def test_eureka_client_none_returns_error_dict(self) -> None:
        settings = make_settings()
        registrar = EurekaRegistrar(settings)
        with patch("app.infrastructure.clients.eureka.eureka_client", None):
            result = await registrar.register()
        assert result["registered"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# register() — success paths
# ---------------------------------------------------------------------------


class TestEurekaRegisterSuccess:
    @pytest.mark.asyncio
    async def test_success_first_attempt(self) -> None:
        settings = make_settings()
        registrar = EurekaRegistrar(settings)
        mock_client = AsyncMock()
        mock_client.init_async = AsyncMock()

        with (
            patch("app.infrastructure.clients.eureka.eureka_client", mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await registrar.register()

        assert result["enabled"] is True
        assert result["registered"] is True
        mock_client.init_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_on_second_attempt_after_first_fails(self) -> None:
        settings = make_settings(EUREKA_REGISTER_MAX_RETRIES=3)
        registrar = EurekaRegistrar(settings)

        call_count = 0

        async def init_async_side_effect(**kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("connection refused")

        mock_client = MagicMock()
        mock_client.init_async = AsyncMock(side_effect=init_async_side_effect)

        with (
            patch("app.infrastructure.clients.eureka.eureka_client", mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await registrar.register()

        assert result["registered"] is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_sets_registered_true_on_success(self) -> None:
        settings = make_settings()
        registrar = EurekaRegistrar(settings)
        mock_client = AsyncMock()
        mock_client.init_async = AsyncMock()

        with (
            patch("app.infrastructure.clients.eureka.eureka_client", mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await registrar.register()

        assert registrar._registered is True


# ---------------------------------------------------------------------------
# register() — retries exhausted
# ---------------------------------------------------------------------------


class TestEurekaRetries:
    @pytest.mark.asyncio
    async def test_all_retries_exhausted_returns_registered_false(self) -> None:
        settings = make_settings(EUREKA_REGISTER_MAX_RETRIES=2)
        registrar = EurekaRegistrar(settings)
        mock_client = MagicMock()
        mock_client.init_async = AsyncMock(side_effect=RuntimeError("always fails"))

        with (
            patch("app.infrastructure.clients.eureka.eureka_client", mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await registrar.register()

        assert result["registered"] is False
        assert "error" in result
        assert mock_client.init_async.call_count == 2


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------


class TestEurekaStop:
    @pytest.mark.asyncio
    async def test_stop_not_called_when_not_registered(self) -> None:
        settings = make_settings()
        registrar = EurekaRegistrar(settings)
        registrar._registered = False
        mock_client = AsyncMock()
        mock_client.stop_async = AsyncMock()

        with patch("app.infrastructure.clients.eureka.eureka_client", mock_client):
            await registrar.stop()

        mock_client.stop_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_called_when_registered(self) -> None:
        settings = make_settings()
        registrar = EurekaRegistrar(settings)
        registrar._registered = True
        mock_client = AsyncMock()
        mock_client.stop_async = AsyncMock()

        with patch("app.infrastructure.clients.eureka.eureka_client", mock_client):
            await registrar.stop()

        mock_client.stop_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_async_raises_does_not_propagate(self) -> None:
        settings = make_settings()
        registrar = EurekaRegistrar(settings)
        registrar._registered = True
        mock_client = MagicMock()
        mock_client.stop_async = AsyncMock(side_effect=RuntimeError("stop error"))

        with patch("app.infrastructure.clients.eureka.eureka_client", mock_client):
            await registrar.stop()  # must not raise
