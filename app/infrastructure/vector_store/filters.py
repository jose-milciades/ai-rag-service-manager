"""Filtros de metadata compartidos por el vector store real (Milvus) y el de memoria.

Contrato retrocompatible: ``{"clave": valor}`` sigue siendo igualdad exacta.
Ademas, cuando el valor es un diccionario cuyas claves empiezan con ``$`` se
interpretan operadores (misma sintaxis que el filtro de Pinecone que usaba
``edi-ai-analysis-ai``): ``$eq``, ``$ne``, ``$in``, ``$nin``, ``$lt``, ``$lte``,
``$gt``, ``$gte``. Un diccionario sin operadores ``$`` conserva el trato de
igualdad de siempre, asi que ningun consumidor actual cambia.

Las claves se validan (``^\\w+$`` ASCII) porque se interpolan en la expresion de
Milvus; los valores siempre se serializan con ``json.dumps``.
"""

import json
import re
from typing import Any

_SAFE_KEY_PATTERN = re.compile(r"^\w+$", re.ASCII)
_COMPARISON = {"$lt": "<", "$lte": "<=", "$gt": ">", "$gte": ">="}
_LIST_OPERATORS = {"$in", "$nin"}
_OPERATORS = {"$eq", "$ne", *_COMPARISON, *_LIST_OPERATORS}
_MAX_LIST_ITEMS = 1000


def is_operator_filter(value: Any) -> bool:
    """True si ``value`` es un dict de operadores ``$...``."""
    return isinstance(value, dict) and bool(value) and all(str(k).startswith("$") for k in value)


def _validate_operator(operator: str, operand: Any) -> None:
    if operator not in _OPERATORS:
        raise ValueError(f"Unsupported filter operator: {operator!r}")
    if operator in _LIST_OPERATORS:
        if not isinstance(operand, list) or len(operand) > _MAX_LIST_ITEMS:
            raise ValueError(f"{operator} requires a list of at most {_MAX_LIST_ITEMS} items")
    elif operator in _COMPARISON and (
        isinstance(operand, bool) or not isinstance(operand, int | float)
    ):
        raise ValueError(f"{operator} requires a numeric value")


def build_milvus_expression(
    filter_conditions: dict[str, Any] | None, payload_field: str = "payload"
) -> str:
    """Traduce las condiciones a una expresion de filtro de Milvus (campo JSON)."""
    if not filter_conditions:
        return ""
    clauses: list[str] = []
    for key, value in filter_conditions.items():
        if not _SAFE_KEY_PATTERN.match(key):
            raise ValueError(f"Unsupported filter key: {key!r}")
        field = f'{payload_field}["{key}"]'
        if not is_operator_filter(value):
            clauses.append(f"{field} == {json.dumps(value)}")
            continue
        for operator, operand in value.items():
            _validate_operator(operator, operand)
            if operator == "$eq":
                clauses.append(f"{field} == {json.dumps(operand)}")
            elif operator == "$ne":
                # como en Pinecone, un registro sin la clave tambien cumple "distinto de"
                clauses.append(f"(not exists {field} or {field} != {json.dumps(operand)})")
            elif operator == "$in":
                clauses.append(f"{field} in {json.dumps(operand)}")
            elif operator == "$nin":
                clauses.append(f"(not exists {field} or {field} not in {json.dumps(operand)})")
            else:
                clauses.append(f"{field} {_COMPARISON[operator]} {json.dumps(operand)}")
    return " and ".join(clauses)


def matches(payload: dict[str, Any], filter_conditions: dict[str, Any] | None) -> bool:
    """Evalua las mismas condiciones en Python (vector store en memoria y pruebas)."""
    if not filter_conditions:
        return True
    for key, value in filter_conditions.items():
        if not _SAFE_KEY_PATTERN.match(key):
            raise ValueError(f"Unsupported filter key: {key!r}")
        present = key in payload
        current = payload.get(key)
        if not is_operator_filter(value):
            if current != value:
                return False
            continue
        for operator, operand in value.items():
            _validate_operator(operator, operand)
            if operator == "$eq" and current != operand:
                return False
            if operator == "$ne" and present and current == operand:
                return False
            if operator == "$in" and current not in operand:
                return False
            if operator == "$nin" and present and current in operand:
                return False
            if operator in _COMPARISON:
                if not isinstance(current, int | float) or isinstance(current, bool):
                    return False
                if not _compare(current, operator, operand):
                    return False
    return True


def _compare(current: float, operator: str, operand: float) -> bool:
    if operator == "$lt":
        return current < operand
    if operator == "$lte":
        return current <= operand
    if operator == "$gt":
        return current > operand
    return current >= operand
