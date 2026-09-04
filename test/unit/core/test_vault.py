"""Tests for app.core.vault — _is_truthy, is_vault_configured, VaultClient, get_vault_client."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.vault import (
    VaultClient,
    _is_truthy,
    get_vault_client,
    is_vault_configured,
)

# ---------------------------------------------------------------------------
# _is_truthy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", "yes", "YES", "on", "ON"])
def test_is_truthy_truthy_values(value: str):
    assert _is_truthy(value) is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "off", "no", "", "random"])
def test_is_truthy_falsy_values(value: str):
    assert _is_truthy(value) is False


def test_is_truthy_none():
    # None → str(None) == "none", not in truthy set
    assert _is_truthy(None) is False


# ---------------------------------------------------------------------------
# is_vault_configured
# ---------------------------------------------------------------------------


def test_is_vault_configured_true(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_VAULT_CONFIG", "true")
    assert is_vault_configured() is True


def test_is_vault_configured_false_explicit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_VAULT_CONFIG", "false")
    assert is_vault_configured() is False


def test_is_vault_configured_absent(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("USE_VAULT_CONFIG", raising=False)
    assert is_vault_configured() is False


def test_is_vault_configured_value_1(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_VAULT_CONFIG", "1")
    assert is_vault_configured() is True


# ---------------------------------------------------------------------------
# VaultClient.__init__ — missing env vars
# ---------------------------------------------------------------------------


def test_vault_client_missing_addr(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    monkeypatch.setenv("VAULT_TOKEN", "s.test")
    with pytest.raises(ValueError, match="VAULT_ADDR"):
        VaultClient()


def test_vault_client_missing_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="VAULT_TOKEN"):
        VaultClient()


def test_vault_client_both_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    with pytest.raises(ValueError) as exc_info:
        VaultClient()
    msg = str(exc_info.value)
    assert "VAULT_ADDR" in msg
    assert "VAULT_TOKEN" in msg


# ---------------------------------------------------------------------------
# VaultClient.__init__ — connection / auth failures
# ---------------------------------------------------------------------------


def test_vault_client_connection_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.setenv("VAULT_TOKEN", "s.test")
    monkeypatch.delenv("VAULT_SKIP_VERIFY", raising=False)

    mock_hvac = MagicMock()
    mock_hvac.is_authenticated.side_effect = Exception("connection refused")

    with (
        patch("app.core.vault.hvac.Client", return_value=mock_hvac),
        pytest.raises(ValueError, match="Vault connection failed"),
    ):
        VaultClient()


def test_vault_client_not_authenticated(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.setenv("VAULT_TOKEN", "s.invalid")
    monkeypatch.delenv("VAULT_SKIP_VERIFY", raising=False)

    mock_hvac = MagicMock()
    mock_hvac.is_authenticated.return_value = False

    with (
        patch("app.core.vault.hvac.Client", return_value=mock_hvac),
        pytest.raises(ValueError, match="Vault authentication failed"),
    ):
        VaultClient()


# ---------------------------------------------------------------------------
# VaultClient.get_secret
# ---------------------------------------------------------------------------


def test_vault_client_get_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.setenv("VAULT_TOKEN", "s.test")
    monkeypatch.delenv("VAULT_SKIP_VERIFY", raising=False)

    mock_hvac = MagicMock()
    mock_hvac.is_authenticated.return_value = True
    mock_hvac.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"KEY": "value", "OTHER": "42"}}
    }

    with patch("app.core.vault.hvac.Client", return_value=mock_hvac):
        client = VaultClient()
        result = client.get_secret("my/path")

    assert result == {"KEY": "value", "OTHER": "42"}


# ---------------------------------------------------------------------------
# VaultClient.load_configs
# ---------------------------------------------------------------------------


def test_vault_client_load_configs_merges_paths(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.setenv("VAULT_TOKEN", "s.test")
    monkeypatch.delenv("VAULT_SKIP_VERIFY", raising=False)

    mock_hvac = MagicMock()
    mock_hvac.is_authenticated.return_value = True

    # Simulate two paths; second overrides "SHARED"
    responses = {
        "path/one": {"data": {"data": {"SHARED": "first", "ONLY_ONE": "yes"}}},
        "path/two": {"data": {"data": {"SHARED": "second", "ONLY_TWO": "yes"}}},
    }
    mock_hvac.secrets.kv.v2.read_secret_version.side_effect = lambda path: responses[path]

    with patch("app.core.vault.hvac.Client", return_value=mock_hvac):
        client = VaultClient()
        result = client.load_configs(["path/one", "path/two"])

    assert result["SHARED"] == "second"
    assert result["ONLY_ONE"] == "yes"
    assert result["ONLY_TWO"] == "yes"


def test_vault_client_load_configs_empty_paths(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.setenv("VAULT_TOKEN", "s.test")
    monkeypatch.delenv("VAULT_SKIP_VERIFY", raising=False)

    mock_hvac = MagicMock()
    mock_hvac.is_authenticated.return_value = True

    with patch("app.core.vault.hvac.Client", return_value=mock_hvac):
        client = VaultClient()
        result = client.load_configs([])

    assert result == {}


# ---------------------------------------------------------------------------
# VAULT_SKIP_VERIFY — disables urllib3 warnings
# ---------------------------------------------------------------------------


def test_vault_skip_verify_disables_warnings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.setenv("VAULT_TOKEN", "s.test")
    monkeypatch.setenv("VAULT_SKIP_VERIFY", "true")

    mock_hvac = MagicMock()
    mock_hvac.is_authenticated.return_value = True

    with (
        patch("app.core.vault.hvac.Client", return_value=mock_hvac),
        patch("app.core.vault.urllib3.disable_warnings") as mock_disable,
    ):
        VaultClient()

    mock_disable.assert_called_once()


# ---------------------------------------------------------------------------
# get_vault_client — lru_cache
# ---------------------------------------------------------------------------


def test_get_vault_client_same_instance(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.setenv("VAULT_TOKEN", "s.test")
    monkeypatch.delenv("VAULT_SKIP_VERIFY", raising=False)

    mock_hvac = MagicMock()
    mock_hvac.is_authenticated.return_value = True

    get_vault_client.cache_clear()
    try:
        with patch("app.core.vault.hvac.Client", return_value=mock_hvac):
            c1 = get_vault_client()
            c2 = get_vault_client()
        assert c1 is c2
    finally:
        get_vault_client.cache_clear()
