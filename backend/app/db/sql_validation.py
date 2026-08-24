"""Validate read-only SQL before execution against a project database."""

from __future__ import annotations

import re

_FORBIDDEN = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|create|truncate|grant|revoke|"
    r"merge|replace|call|execute|copy|vacuum|analyze|comment|"
    r"attach|detach|pragma|reindex|refresh|security|set\b"
    r")\b",
    re.IGNORECASE,
)


def validate_readonly_sql(sql: str) -> str:
    """Return normalized SQL or raise ValueError."""
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        raise ValueError("SQL query is empty.")

    if ";" in text:
        raise ValueError("Only a single SQL statement is allowed.")

    lowered = text.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("Only read-only SELECT / WITH queries are allowed.")

    if _FORBIDDEN.search(text):
        raise ValueError("Only read-only SELECT queries are allowed.")

    return text
