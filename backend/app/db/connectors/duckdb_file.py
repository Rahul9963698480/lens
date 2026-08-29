"""DuckDB file connector for xlsx projects — local cached file, no per-query network."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import duckdb

from app.config import settings
from app.db.connectors.base import DBConnector
from app.db.sql_validation import validate_readonly_sql, wrap_sql_row_limit
from app.storage.xlsx_cache import get_cached_local_path
from app.storage.xlsx_indexes import apply_storage_optimizations
from app.storage.xlsx_relationships import (
    infer_relationship_candidates_from_path,
    merge_with_declared,
    verify_relationship_candidates,
)

RelationshipVerifier = Callable[[dict[str, Any]], bool | Awaitable[bool]]

QUERY_TIMEOUT_SECONDS = 30.0

#Helper functions
# Wraps table and column names in double quotes ("My Table") so spaces, special characters, or reserved keywords don't cause SQL syntax errors
def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'

# This Converts raw values returned by DuckDB into JSON-safe formats (e.g., converting datetime objects to ISO strings, binary bytes to hex strings).
def _serialize_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (bytes, memoryview)):
        return bytes(value).hex()
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)

#Apply memory and thread limits to the DuckDB connection.
def _configure_connection(conn: duckdb.DuckDBPyConnection) -> None:
    if settings.DUCKDB_MEMORY_LIMIT:
        conn.execute(f"SET memory_limit = '{settings.DUCKDB_MEMORY_LIMIT}'")
    if settings.DUCKDB_THREADS > 0:
        conn.execute(f"SET threads = {int(settings.DUCKDB_THREADS)}")

# DuckDB File Connector for xlsx projects 
class DuckDBFileConnector(DBConnector):
    def __init__(
        self,
        project_id: str,
        storage_path: str,
        *,
        relationship_verifier: RelationshipVerifier | None = None,
    ) -> None:
        self.project_id = project_id
        self.storage_path = storage_path
        self.relationship_verifier = relationship_verifier

# Retrieves the cached .duckdb file from local disk. If missing, it downloads it from Supabase storage first.
    async def _get_local_path(self) -> str:
        return await get_cached_local_path(self.project_id, self.storage_path)

# checks whether DuckDB can access the project. Used to check the file is reachable after upload/cache.
    async def test_connection(self) -> tuple[bool, str]:
        try:
            path = await self._get_local_path()

            def _run() -> None:
                conn = duckdb.connect(path, read_only=True)
                try:
                    _configure_connection(conn)
                    conn.execute("SELECT 1")
                finally:
                    conn.close()

            await asyncio.to_thread(_run)
            return True, ""
        except Exception as exc:
            return False, f"Could not access project data: {exc}"

# Queries DuckDB's system catalog (information_schema.tables) to return all tables (representing Excel sheets).
    async def list_tables(self) -> list[str]:
        path = await self._get_local_path()
        return await asyncio.to_thread(self._list_tables_sync, path)

    def _list_tables_sync(self, path: str) -> list[str]:
        conn = duckdb.connect(path, read_only=True)
        try:
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
        finally:
            conn.close()
            
# Returns the first N rows from a specific table (sheet). Used to generate preview data for the UI.
    async def preview_table(self, table_name: str, limit: int = 10) -> dict[str, Any]:
        try:
            tables = await self.list_tables()
            if table_name not in tables:
                return {"columns": [], "error": f"Table {table_name!r} not found."}
            path = await self._get_local_path()
            return await asyncio.to_thread(
                self._preview_table_sync, path, table_name, limit
            )
        except Exception as exc:
            return {"columns": [], "error": str(exc)}
            

    def _preview_table_sync(self, path: str, table_name: str, limit: int) -> dict[str, Any]:
        conn = duckdb.connect(path, read_only=True)
        try:
            _configure_connection(conn)
            records = conn.execute(
                f"SELECT * FROM {_quote_ident(table_name)} LIMIT {int(limit)}"
            ).fetchdf()
            if records.empty:
                info = conn.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'main'
                      AND table_name = ?
                    ORDER BY ordinal_position
                    """,
                    [table_name],
                ).fetchall()
                columns = [str(r[0]) for r in info]
                return {"columns": columns, "rows": []}
            columns = list(records.columns)
            rows = [
                {col: _serialize_value(records.iloc[i][col]) for col in columns}
                for i in range(len(records))
            ]
            return {"columns": columns, "rows": rows}
        finally:
            conn.close()
# Returns a structured schema including table definitions and detected relationships. This describes the Excel workbook as a database
    async def get_schema(self) -> dict[str, Any]:
        path = await self._get_local_path()
        tables, table_names = await asyncio.to_thread(self._read_table_metadata_sync, path)
        candidates = await asyncio.to_thread(
            infer_relationship_candidates_from_path, path, table_names
        )
        inferred = await verify_relationship_candidates(
            candidates,
            verifier=self.relationship_verifier,
        )
        primary_keys = await asyncio.to_thread(
            self._apply_indexes_sync, path, table_names, inferred
        )
        for table in tables:
            pk_col = primary_keys.get(table["table_name"])
            if not pk_col:
                continue
            for col in table["columns"]:
                if col["name"] == pk_col:
                    col["primary_key"] = True
                    break
        return {
            "tables": tables,
            "relationships": merge_with_declared([], inferred),
        }

    def _read_table_metadata_sync(
        self, path: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        conn = duckdb.connect(path, read_only=True)
        try:
            table_names = self._table_names(conn)
            column_rows = conn.execute(
                """
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'main'
                ORDER BY table_name, ordinal_position
                """
            ).fetchall()
            columns_by_table: dict[str, list[dict[str, Any]]] = {}
            for table_name, col_name, data_type, is_nullable in column_rows:
                table = str(table_name)
                columns_by_table.setdefault(table, []).append(
                    {
                        "name": str(col_name),
                        "type": str(data_type) if data_type else "VARCHAR",
                        "nullable": str(is_nullable).upper() == "YES",
                        "primary_key": False,
                        "foreign_key": None,
                    }
                )
            tables = [
                {
                    "table_name": table_name,
                    "columns": columns_by_table.get(table_name, []),
                    "inferred": True,
                }
                for table_name in table_names
            ]
            return tables, table_names
        finally:
            conn.close()

    def _apply_indexes_sync(
        self,
        path: str,
        table_names: list[str],
        relationships: list[dict[str, Any]],
    ) -> dict[str, str]:
        conn = duckdb.connect(path)
        try:
            _configure_connection(conn)
            return apply_storage_optimizations(
                conn, relationships, tables=table_names
            )
        finally:
            conn.close()
# Executes read-only SQL queries generated by the AI agent or typed by the user.
    async def execute_query(self, sql: str, *, max_rows: int = 1000) -> dict[str, Any]:
        query = validate_readonly_sql(sql)
        path = await self._get_local_path()

        def _run() -> dict[str, Any]:
            conn = duckdb.connect(path, read_only=True)
            try:
                _configure_connection(conn)
                df = conn.execute(wrap_sql_row_limit(query, max_rows)).fetchdf()
                columns = list(df.columns)
                rows = [
                    {col: _serialize_value(row[col]) for col in columns}
                    for _, row in df.iterrows()
                ]
                return {
                    "status": "ok",
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                }
            finally:
                conn.close()

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_run), timeout=QUERY_TIMEOUT_SECONDS
            )
        except TimeoutError as exc:
            raise ValueError("Query timed out.") from exc
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Could not execute query: {exc}") from exc

    def _table_names(self, conn: duckdb.DuckDBPyConnection) -> list[str]:
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
