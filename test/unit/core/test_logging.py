"""Tests for app.core.logging — CorrelationIdFilter, configure_logging, get_logger."""

import logging
import os

import pytest

from app.core.config import get_settings
from app.core.logging import (
    CorrelationIdFilter,
    configure_logging,
    correlation_id_var,
    get_logger,
)

# ---------------------------------------------------------------------------
# CorrelationIdFilter.filter
# ---------------------------------------------------------------------------


def test_correlation_id_filter_sets_from_context_var():
    token = correlation_id_var.set("test-cid-123")
    try:
        f = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        result = f.filter(record)
        assert result is True
        assert record.correlation_id == "test-cid-123"
    finally:
        correlation_id_var.reset(token)


def test_correlation_id_filter_default_when_no_context():
    # Reset to the ContextVar default ("-")
    token = correlation_id_var.set("-")
    try:
        f = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        f.filter(record)
        assert record.correlation_id == "-"
    finally:
        correlation_id_var.reset(token)


def test_correlation_id_filter_always_returns_true():
    f = CorrelationIdFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="msg",
        args=(),
        exc_info=None,
    )
    assert f.filter(record) is True


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


def test_configure_logging_creates_logs_directory(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """configure_logging must create logs/ relative to cwd; use tmp_path as cwd."""
    monkeypatch.setenv("USE_VAULT_CONFIG", "false")
    monkeypatch.setenv("DEBUG", "false")
    get_settings.cache_clear()
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        configure_logging()
        assert (tmp_path / "logs").is_dir()
    finally:
        os.chdir(original_dir)
        get_settings.cache_clear()


def test_configure_logging_does_not_raise_on_repeated_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    monkeypatch.setenv("USE_VAULT_CONFIG", "false")
    monkeypatch.setenv("DEBUG", "false")
    get_settings.cache_clear()
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        configure_logging()
        configure_logging()  # second call must not raise
    finally:
        os.chdir(original_dir)
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


def test_get_logger_returns_logger_with_correct_name():
    logger = get_logger("my.module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "my.module"


def test_get_logger_same_as_standard_getlogger():
    assert get_logger("foo.bar") is logging.getLogger("foo.bar")
