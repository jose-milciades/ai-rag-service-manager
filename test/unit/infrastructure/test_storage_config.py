"""Unit tests for StorageConfig."""

import json

import pytest

from app.core.config import Settings
from app.infrastructure.clients.storage_config import StorageConfig


def make_settings(**kwargs: object) -> Settings:
    defaults: dict[str, object] = {
        "RAG_ENVIRONMENT": "edi-local",
        "RAG_EMBEDDING_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test",
        "DEBUG": False,
    }
    defaults.update(kwargs)
    return Settings(**defaults)


VALID_CREDS = json.dumps(
    {
        "type": "service_account",
        "project_id": "my-project",
        "private_key_id": "key-id",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
        "client_email": "sa@my-project.iam.gserviceaccount.com",
        "client_id": "123456789",
    }
)


# ---------------------------------------------------------------------------
# __init__ — basic construction
# ---------------------------------------------------------------------------


class TestStorageConfigInit:
    def test_no_credentials_leaves_credentials_info_none(self) -> None:
        settings = make_settings(GOOGLE_CREDS_JSON=None)
        cfg = StorageConfig(settings)
        assert cfg.credentials_info is None

    def test_empty_string_creds_leaves_credentials_info_none(self) -> None:
        settings = make_settings(GOOGLE_CREDS_JSON="")
        cfg = StorageConfig(settings)
        assert cfg.credentials_info is None

    def test_valid_json_credentials_are_loaded(self) -> None:
        settings = make_settings(GOOGLE_CREDS_JSON=VALID_CREDS, STORAGE_PROJECT_ID="my-project")
        cfg = StorageConfig(settings)
        assert cfg.credentials_info is not None
        assert cfg.credentials_info["project_id"] == "my-project"

    def test_invalid_json_raises_value_error(self) -> None:
        settings = make_settings(GOOGLE_CREDS_JSON="{not: valid json", STORAGE_PROJECT_ID="p")
        with pytest.raises(ValueError, match="valid JSON"):
            StorageConfig(settings)

    def test_json_not_a_dict_raises_type_error(self) -> None:
        settings = make_settings(GOOGLE_CREDS_JSON='["a", "b"]', STORAGE_PROJECT_ID="p")
        with pytest.raises(TypeError, match="JSON object"):
            StorageConfig(settings)

    def test_credentials_without_project_id_raises_value_error(self) -> None:
        creds_no_project = json.dumps(
            {
                "type": "service_account",
                "private_key": "fake",
                "client_email": "sa@x.iam.gserviceaccount.com",
            }
        )
        settings = make_settings(GOOGLE_CREDS_JSON=creds_no_project, STORAGE_PROJECT_ID=None)
        with pytest.raises(ValueError, match="project_id"):
            StorageConfig(settings)

    def test_storage_project_id_setting_takes_precedence(self) -> None:
        settings = make_settings(
            GOOGLE_CREDS_JSON=VALID_CREDS,
            STORAGE_PROJECT_ID="override-project",
        )
        cfg = StorageConfig(settings)
        assert cfg.project_id == "override-project"


# ---------------------------------------------------------------------------
# _get_project_id_from_credentials_info
# ---------------------------------------------------------------------------


class TestGetProjectIdFromCredentialsInfo:
    def test_project_id_in_json_is_returned(self) -> None:
        settings = make_settings(GOOGLE_CREDS_JSON=VALID_CREDS)
        cfg = StorageConfig(settings)
        assert cfg._get_project_id_from_credentials_info() == "my-project"

    def test_no_credentials_info_returns_none(self) -> None:
        settings = make_settings(GOOGLE_CREDS_JSON=None)
        cfg = StorageConfig(settings)
        assert cfg._get_project_id_from_credentials_info() is None


# ---------------------------------------------------------------------------
# has_credentials_info
# ---------------------------------------------------------------------------


class TestHasCredentialsInfo:
    def test_true_when_credentials_loaded(self) -> None:
        settings = make_settings(GOOGLE_CREDS_JSON=VALID_CREDS, STORAGE_PROJECT_ID="my-project")
        cfg = StorageConfig(settings)
        assert cfg.has_credentials_info() is True

    def test_false_when_no_credentials(self) -> None:
        settings = make_settings(GOOGLE_CREDS_JSON=None)
        cfg = StorageConfig(settings)
        assert cfg.has_credentials_info() is False
