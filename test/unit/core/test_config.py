"""Tests for app.core.config — Settings validators, _vault_config_paths, get_settings."""

import pytest

from app.core.config import Settings, _vault_config_paths, get_settings

# Minimum kwargs to build a valid Settings without picking up bad env-var values
# from the test process environment (e.g. DEBUG=release set by the shell).
_SAFE_KWARGS: dict = {
    "DEBUG": False,
    "RAG_ENVIRONMENT": "edi-local",
    "RAG_EMBEDDING_PROVIDER": "openai",
}


# ---------------------------------------------------------------------------
# Settings._blank_optional_int_as_none
# ---------------------------------------------------------------------------


def test_blank_optional_int_as_none_empty_string():
    s = Settings(**_SAFE_KWARGS, RAG_OPENAI_EMBEDDING_DIMENSIONS="")
    assert s.rag_openai_embedding_dimensions is None


def test_blank_optional_int_as_none_valid_int():
    s = Settings(**_SAFE_KWARGS, RAG_OPENAI_EMBEDDING_DIMENSIONS="256")
    assert s.rag_openai_embedding_dimensions == 256


def test_blank_optional_int_as_none_explicit_none():
    s = Settings(**_SAFE_KWARGS, RAG_OPENAI_EMBEDDING_DIMENSIONS=None)
    assert s.rag_openai_embedding_dimensions is None


# ---------------------------------------------------------------------------
# Settings._validate_rag_environment
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["edi-local", "edi-dev", "edi-stage", "edi-prod"])
def test_validate_rag_environment_valid(value: str):
    s = Settings(DEBUG=False, RAG_ENVIRONMENT=value, RAG_EMBEDDING_PROVIDER="openai")
    assert s.rag_environment == value


def test_validate_rag_environment_invalid():
    with pytest.raises(ValueError, match="RAG_ENVIRONMENT invalido"):
        Settings(DEBUG=False, RAG_ENVIRONMENT="production", RAG_EMBEDDING_PROVIDER="openai")


# ---------------------------------------------------------------------------
# Settings._validate_rag_embedding_provider
# ---------------------------------------------------------------------------


def test_validate_rag_embedding_provider_openai():
    s = Settings(DEBUG=False, RAG_ENVIRONMENT="edi-local", RAG_EMBEDDING_PROVIDER="openai")
    assert s.rag_embedding_provider == "openai"


def test_validate_rag_embedding_provider_invalid():
    with pytest.raises(ValueError, match="RAG_EMBEDDING_PROVIDER invalido"):
        Settings(DEBUG=False, RAG_ENVIRONMENT="edi-local", RAG_EMBEDDING_PROVIDER="local")


# ---------------------------------------------------------------------------
# _vault_config_paths
# ---------------------------------------------------------------------------


def test_vault_config_paths_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("VAULT_CONFIG_PATHS", raising=False)
    paths = _vault_config_paths()
    assert paths == ["common", "ai-rag-service-manager", "storage", "llm_apis"]


def test_vault_config_paths_custom_env_var(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_CONFIG_PATHS", "path-a, path-b , path-c")
    paths = _vault_config_paths()
    assert paths == ["path-a", "path-b", "path-c"]


def test_vault_config_paths_single_entry(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_CONFIG_PATHS", "only-path")
    assert _vault_config_paths() == ["only-path"]


def test_vault_config_paths_strips_empty_segments(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_CONFIG_PATHS", "a,,b,")
    assert _vault_config_paths() == ["a", "b"]


# ---------------------------------------------------------------------------
# get_settings() — lru_cache behaviour
# ---------------------------------------------------------------------------


def test_get_settings_returns_same_instance(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_VAULT_CONFIG", "false")
    monkeypatch.setenv("DEBUG", "false")
    get_settings.cache_clear()
    try:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
    finally:
        get_settings.cache_clear()


def test_get_settings_no_vault_reads_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_VAULT_CONFIG", "false")
    monkeypatch.setenv("DEBUG", "false")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert isinstance(settings, Settings)
        assert settings.rag_environment in {"edi-local", "edi-dev", "edi-stage", "edi-prod"}
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Settings field aliases (AliasChoices)
# ---------------------------------------------------------------------------


def test_field_alias_eureka_server():
    """EUREKA_SERVER and EUREKA_SERVER_URL both map to eureka_server_url."""
    s1 = Settings(**_SAFE_KWARGS, EUREKA_SERVER_URL="http://eureka1:8761/eureka/")
    s2 = Settings(**_SAFE_KWARGS, EUREKA_SERVER="http://eureka2:8761/eureka/")
    assert s1.eureka_server_url == "http://eureka1:8761/eureka/"
    assert s2.eureka_server_url == "http://eureka2:8761/eureka/"


def test_field_alias_app_host():
    """API_HOST and APP_HOST both map to app_host."""
    s1 = Settings(**_SAFE_KWARGS, APP_HOST="1.2.3.4")
    s2 = Settings(**_SAFE_KWARGS, API_HOST="5.6.7.8")
    assert s1.app_host == "1.2.3.4"
    assert s2.app_host == "5.6.7.8"


def test_field_alias_app_port():
    """APP_PORT and API_PORT both map to app_port."""
    s1 = Settings(**_SAFE_KWARGS, APP_PORT="9000")
    s2 = Settings(**_SAFE_KWARGS, API_PORT="9001")
    assert s1.app_port == 9000
    assert s2.app_port == 9001
