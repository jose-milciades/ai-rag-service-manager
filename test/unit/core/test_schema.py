"""Tests for app.core.schema — to_camel, get_camel_case_config."""

from pydantic import BaseModel

from app.core.schema import get_camel_case_config, to_camel

# ---------------------------------------------------------------------------
# to_camel
# ---------------------------------------------------------------------------


def test_to_camel_single_underscore():
    assert to_camel("file_name") == "fileName"


def test_to_camel_no_underscore():
    assert to_camel("id") == "id"


def test_to_camel_multiple_underscores():
    assert to_camel("text_preview") == "textPreview"


def test_to_camel_three_segments():
    assert to_camel("some_long_field") == "someLongField"


def test_to_camel_leading_lowercase_preserved():
    assert to_camel("myField") == "myField"


# ---------------------------------------------------------------------------
# get_camel_case_config
# ---------------------------------------------------------------------------


def test_get_camel_case_config_has_alias_generator():
    cfg = get_camel_case_config()
    assert "alias_generator" in cfg
    assert cfg["alias_generator"] is to_camel


def test_get_camel_case_config_populate_by_name():
    cfg = get_camel_case_config()
    assert cfg.get("populate_by_name") is True


def test_get_camel_case_config_use_enum_values():
    cfg = get_camel_case_config()
    assert cfg.get("use_enum_values") is True


def test_get_camel_case_config_extra_kwargs_forwarded():
    cfg = get_camel_case_config(frozen=True)
    assert cfg.get("frozen") is True


# ---------------------------------------------------------------------------
# Pydantic model integration — camelCase serialization
# ---------------------------------------------------------------------------


class _SampleModel(BaseModel):
    model_config = get_camel_case_config()

    file_name: str
    text_preview: str
    record_id: int


def test_model_serializes_with_camel_case_keys():
    m = _SampleModel(file_name="doc.pdf", text_preview="hello", record_id=1)
    data = m.model_dump(by_alias=True)
    assert "fileName" in data
    assert "textPreview" in data
    assert "recordId" in data
    assert data["fileName"] == "doc.pdf"


def test_model_can_be_constructed_by_snake_case():
    """populate_by_name=True means snake_case construction still works."""
    m = _SampleModel(file_name="a.txt", text_preview="p", record_id=2)
    assert m.file_name == "a.txt"


def test_model_can_be_constructed_by_camel_case():
    """alias_generator means camelCase keys also work for construction."""
    m = _SampleModel.model_validate({"fileName": "b.txt", "textPreview": "q", "recordId": 3})
    assert m.file_name == "b.txt"
