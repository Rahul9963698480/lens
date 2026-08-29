"""Infer primary keys and create indexes on xlsx DuckDB files."""

from __future__ import annotations

import re
from typing import Any

import duckdb

PK_UNIQUENESS_THRESHOLD = 0.95
_ID_NAME_RE = re.compile(r"^(id|.*_id)$", re.IGNORECASE)

_SKIP_INDEX_TYPES = frozenset(
    {"REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL", "BLOB", "BYTEA"}
)


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _safe_index_name(table: str, column: str, *, suffix: str = "idx") -> str:
    raw = f"{suffix}_{table}_{column}"
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)[:63]


def _column_type(raw: str | None) -> str:
    return (raw or "VARCHAR").strip().upper() or "VARCHAR"


def _list_tables(conn: duckdb.DuckDBPyConnection) -> list[str]:
    rows = conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    ).fetchall()
    return [str(r[0]) for r in rows]


def _list_columns(conn: duckdb.DuckDBPyConnection, table: str) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'main'
          AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table],
    ).fetchall()
    return [(str(r[0]), _column_type(r[1])) for r in rows]


def _uniqueness_ratio(conn: duckdb.DuckDBPyConnection, table: str, column: str) -> float:
    row_count = conn.execute(
        f"SELECT COUNT(*) FROM {_quote_ident(table)}"
    ).fetchone()[0]
    if not row_count:
        return 0.0
    distinct_count = conn.execute(
        f"SELECT COUNT(DISTINCT {_quote_ident(column)}) "
        f"FROM {_quote_ident(table)} "
        f"WHERE {_quote_ident(column)} IS NOT NULL"
    ).fetchone()[0]
    return float(distinct_count) / float(row_count)


def _pk_name_score(column: str) -> float:
    if column.lower() == "id":
        return 0.3
    if _ID_NAME_RE.match(column):
        return 0.15
    return 0.0


def infer_primary_keys(
    conn: duckdb.DuckDBPyConnection,
    tables: list[str] | None = None,
) -> dict[str, str]:
    """Return the best primary-key candidate column per table, if any."""
    table_names = tables or _list_tables(conn)
    result: dict[str, str] = {}
    for table in table_names:
        best_column: str | None = None
        best_score = PK_UNIQUENESS_THRESHOLD
        for column, col_type in _list_columns(conn, table):
            if col_type in _SKIP_INDEX_TYPES:
                continue
            uniqueness = _uniqueness_ratio(conn, table, column)
            score = uniqueness + _pk_name_score(column)
            if uniqueness >= PK_UNIQUENESS_THRESHOLD and score > best_score:
                best_score = score
                best_column = column
        if best_column:
            result[table] = best_column
    return result


def create_primary_key_indexes(
    conn: duckdb.DuckDBPyConnection,
    primary_keys: dict[str, str],
) -> None:
    for table, column in primary_keys.items():
        idx = _safe_index_name(table, column, suffix="pk")
        conn.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {_quote_ident(idx)} "
            f"ON {_quote_ident(table)} ({_quote_ident(column)})"
        )


def create_join_indexes(
    conn: duckdb.DuckDBPyConnection,
    relationships: list[dict[str, Any]],
) -> None:
    seen: set[tuple[str, str]] = set()
    for rel in relationships:
        for table, column in (
            (str(rel["from_table"]), str(rel["from_column"])),
            (str(rel["to_table"]), str(rel["to_column"])),
        ):
            key = (table, column)
            if key in seen:
                continue
            seen.add(key)
            idx = _safe_index_name(table, column)
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {_quote_ident(idx)} "
                f"ON {_quote_ident(table)} ({_quote_ident(column)})"
            )


def apply_storage_optimizations(
    conn: duckdb.DuckDBPyConnection,
    relationships: list[dict[str, Any]],
    *,
    tables: list[str] | None = None,
) -> dict[str, str]:
    """Create PK unique indexes and join indexes. Returns inferred primary keys."""
    primary_keys = infer_primary_keys(conn, tables)
    create_primary_key_indexes(conn, primary_keys)
    create_join_indexes(conn, relationships)
    return primary_keys
