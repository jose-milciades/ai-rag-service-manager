"""Tests for app.core.utils — generate_unique_code, serialize_for_json, now_mx."""

import datetime
import re
from zoneinfo import ZoneInfo

import pytest

from app.core.utils import generate_unique_code, now_mx, serialize_for_json

# ---------------------------------------------------------------------------
# generate_unique_code
# ---------------------------------------------------------------------------


def test_generate_unique_code_non_empty():
    code = generate_unique_code()
    assert isinstance(code, str)
    assert len(code) > 0


def test_generate_unique_code_two_calls_differ():
    assert generate_unique_code() != generate_unique_code()


def test_generate_unique_code_hex_format():
    """Code must contain only hex characters (0-9, a-f)."""
    code = generate_unique_code()
    assert re.fullmatch(r"[0-9a-f]+", code), f"Non-hex chars in code: {code!r}"


def test_generate_unique_code_minimum_length():
    """Timestamp hex (≥ 11 chars for ms epoch) + 8 random hex = at least 19 chars."""
    code = generate_unique_code()
    assert len(code) >= 19


# ---------------------------------------------------------------------------
# serialize_for_json
# ---------------------------------------------------------------------------


def test_serialize_for_json_datetime_to_isoformat():
    dt = datetime.datetime(2024, 6, 15, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
    result = serialize_for_json(dt)
    assert result == dt.isoformat()


def test_serialize_for_json_nested_dict_with_datetime():
    dt = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
    obj = {"created": dt, "name": "test"}
    result = serialize_for_json(obj)
    assert result == {"created": dt.isoformat(), "name": "test"}


def test_serialize_for_json_list_of_datetimes():
    dt1 = datetime.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC"))
    dt2 = datetime.datetime(2024, 6, 1, tzinfo=ZoneInfo("UTC"))
    result = serialize_for_json([dt1, dt2])
    assert result == [dt1.isoformat(), dt2.isoformat()]


def test_serialize_for_json_plain_string_unchanged():
    assert serialize_for_json("hello") == "hello"


def test_serialize_for_json_plain_int_unchanged():
    assert serialize_for_json(42) == 42


def test_serialize_for_json_nested_list_in_dict():
    dt = datetime.datetime(2024, 3, 10, tzinfo=ZoneInfo("UTC"))
    obj = {"items": [dt, "string", 1]}
    result = serialize_for_json(obj)
    assert result == {"items": [dt.isoformat(), "string", 1]}


def test_serialize_for_json_deeply_nested():
    dt = datetime.datetime(2024, 5, 20, tzinfo=ZoneInfo("UTC"))
    obj = {"level1": {"level2": dt}}
    result = serialize_for_json(obj)
    assert result == {"level1": {"level2": dt.isoformat()}}


def test_serialize_for_json_none_unchanged():
    assert serialize_for_json(None) is None


# ---------------------------------------------------------------------------
# now_mx
# ---------------------------------------------------------------------------


def test_now_mx_returns_timezone_aware():
    dt = now_mx()
    assert dt.tzinfo is not None


def test_now_mx_default_timezone():
    dt = now_mx()
    # ZoneInfo key stored as tzinfo.key
    assert hasattr(dt.tzinfo, "key")
    assert dt.tzinfo.key == "America/Mexico_City"  # type: ignore[union-attr]


def test_now_mx_timezone_env_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TIMEZONE", "America/New_York")
    dt = now_mx()
    assert dt.tzinfo is not None
    assert dt.tzinfo.key == "America/New_York"  # type: ignore[union-attr]


def test_now_mx_utc_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TIMEZONE", "UTC")
    dt = now_mx()
    assert dt.tzinfo.key == "UTC"  # type: ignore[union-attr]
