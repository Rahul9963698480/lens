"""Convert an uploaded XLSX workbook into a local SQLite database."""

from __future__ import annotations

import math
import re
import sqlite3
from datetime import date, datetime
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import pandas as pd

_NON_ALNUM = re.compile(r"[^a-z0-9_]+")
_MULTI_UNDERSCORE = re.compile(r"_+")


class XlsxIngestError(ValueError):
    """Workbook could not be parsed into SQLite tables."""


def sanitize_identifier(name: str, *, fallback: str = "col") -> str:
    text = str(name or "").strip().lower()
    text = _NON_ALNUM.sub("_", text)
    text = _MULTI_UNDERSCORE.sub("_", text).strip("_")
    if not text:
        text = fallback
    if text[0].isdigit():
        text = f"{fallback}_{text}"
    return text


def unique_identifier(base: str, used: set[str]) -> str:
    if base not in used:
        used.add(base)
        return base
    index = 2
    while f"{base}_{index}" in used:
        index += 1
    name = f"{base}_{index}"
    used.add(name)
    return name


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _is_integer_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, Integral):
        return True
    if isinstance(value, Real):
        number = float(value)
        return math.isfinite(number) and number.is_integer()
    return False


def _is_numeric(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, Integral):
        return True
    if isinstance(value, Real):
        return math.isfinite(float(value))
    return False


def _is_date_like(value: Any) -> bool:
    return isinstance(value, (datetime, date, pd.Timestamp))


def infer_sqlite_type(series: pd.Series) -> str:
    values = [v for v in series.tolist() if not _is_null(v)]
    if not values:
        return "TEXT"
    if all(_is_integer_like(v) for v in values):
        return "INTEGER"
    if all(_is_numeric(v) for v in values):
        return "REAL"
    if all(_is_date_like(v) for v in values):
        return "TEXT"
    return "TEXT"


def _to_sqlite_value(value: Any, sqlite_type: str) -> Any:
    if _is_null(value):
        return None
    if sqlite_type == "INTEGER":
        return int(value)
    if sqlite_type == "REAL":
        return float(value)
    if _is_date_like(value):
        ts = pd.Timestamp(value)
        if ts.hour == 0 and ts.minute == 0 and ts.second == 0 and ts.microsecond == 0:
            return ts.date().isoformat()
        return ts.isoformat(timespec="seconds")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _prepare_frame(df: pd.Series | pd.DataFrame, table_name: str) -> tuple[pd.DataFrame, list[str], list[str]]:
    if isinstance(df, pd.Series):
        df = df.to_frame()
    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")
    if df.empty:
        raise XlsxIngestError(f"Sheet {table_name!r} has no data rows.")

    used_cols: set[str] = set()
    columns: list[str] = []
    for raw in df.columns:
        base = sanitize_identifier(str(raw), fallback="col")
        columns.append(unique_identifier(base, used_cols))
    df.columns = columns
    types = [infer_sqlite_type(df[col]) for col in columns]
    return df, columns, types


def workbook_to_sqlite(xlsx_path: str | Path, sqlite_path: str | Path) -> list[str]:
    """Parse an .xlsx file into SQLite tables. Returns created table names."""
    path = Path(xlsx_path)
    if path.suffix.lower() != ".xlsx":
        raise XlsxIngestError("Only .xlsx files are supported.")

    try:
        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    except Exception as exc:
        raise XlsxIngestError(
            f"Could not parse the spreadsheet (corrupt or unsupported format): {exc}"
        ) from exc

    if not sheets:
        raise XlsxIngestError("Workbook is empty — no sheets found.")

    sqlite_path = Path(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        sqlite_path.unlink()

    used_tables: set[str] = set()
    created: list[str] = []

    conn = sqlite3.connect(str(sqlite_path))
    try:
        for sheet_name, frame in sheets.items():
            if frame is None or frame.empty:
                continue
            try:
                df, columns, types = _prepare_frame(frame, str(sheet_name))
            except XlsxIngestError:
                continue

            table = unique_identifier(
                sanitize_identifier(str(sheet_name), fallback="sheet"),
                used_tables,
            )
            col_defs = ", ".join(
                f"{_quote_ident(col)} {col_type}" for col, col_type in zip(columns, types)
            )
            conn.execute(f"CREATE TABLE {_quote_ident(table)} ({col_defs})")

            placeholders = ", ".join("?" for _ in columns)
            quoted_cols = ", ".join(_quote_ident(c) for c in columns)
            insert_sql = (
                f"INSERT INTO {_quote_ident(table)} ({quoted_cols}) VALUES ({placeholders})"
            )
            rows = [
                tuple(_to_sqlite_value(row[col], types[i]) for i, col in enumerate(columns))
                for row in df.to_dict(orient="records")
            ]
            conn.executemany(insert_sql, rows)
            created.append(table)

        conn.commit()
    except Exception:
        conn.close()
        if sqlite_path.exists():
            sqlite_path.unlink()
        raise
    else:
        conn.close()

    if not created:
        if sqlite_path.exists():
            sqlite_path.unlink()
        raise XlsxIngestError("Workbook is empty — no sheets with data.")

    return created
