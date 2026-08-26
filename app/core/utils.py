"""Shared functions for state management."""

import datetime
import os
import secrets
import time
from typing import Any
from zoneinfo import ZoneInfo


def generate_unique_code() -> str:
    timestamp = int(time.time() * 1000)
    timestamp_str = format(timestamp, "x")  # base 16 (hex)
    random_part = secrets.token_hex(4)  # 8 caracteres hex aleatorios
    return timestamp_str + random_part


def serialize_for_json(obj: Any) -> Any:
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    return obj


def now_mx() -> datetime.datetime:
    """
    Retorna la hora actual en la zona horaria configurada (por defecto America/Mexico_City).
    """
    tz = os.getenv("TIMEZONE", "America/Mexico_City")
    return datetime.datetime.now(ZoneInfo(tz))
