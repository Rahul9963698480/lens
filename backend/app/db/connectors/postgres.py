"""Postgres external connector — short-lived asyncpg connections only."""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from app.db.connectors.base import DBConnector
from app.db.sql_validation import validate_readonly_sql, wrap_sql_row_limit

STATEMENT_TIMEOUT_MS = 30_000


def _quote_ident(name: str) -> str:
    """Double-quote a Postgres identifier. Names must come from information_schema only."""
    return '"' + name.replace('"', '""') + '"'


def _readable_error(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError) or "timeout" in str(exc).lower():
        return "Connection timed out - check the host and that the database is reachable."

    if isinstance(exc, asyncpg.InvalidPasswordError):
        return "Authentication failed - check the username and password."

    if isinstance(exc, asyncpg.InvalidCatalogNameError):
        return "Database does not exist - check the database name."

    msg = str(exc).lower()

    if "password authentication failed" in msg or "authentication failed" in msg:
        return "Authentication failed - check the username and password."
    if "does not exist" in msg and "database" in msg:
        return "Database does not exist - check the database name."
    if "could not translate host name" in msg or "name or service not known" in msg:
        return "Host unreachable - check the hostname."
    if "connection refused" in msg:
        return "Connection refused - check the host and port."
    if "timeout" in msg or "timed out" in msg:
        return "Connection timed out - check the host and that the database is reachable."
    if "network is unreachable" in msg or "no route to host" in msg:
        return "Host unreachable - check the hostname and network."
    if "ssl" in msg or "tls" in msg or "certificate" in msg:
        return "SSL/TLS required or failed - check that the host supports encrypted connections."

    return "Could not connect to the database - check the connection details."


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


class PostgresConnector(DBConnector):
    def __init__(
        self,
        host: str,
        port: int,
        dbname: str,
        username: str,
        password: str,
        *,
        timeout: float = 5,
        column_limit: int = 5,
    ) -> None:
        self.host = host
        self.port = port
        self.dbname = dbname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.column_limit = column_limit

    async def _connect(self) -> asyncpg.Connection:
        # Managed Postgres (e.g. Supabase) requires TLS; matches app_db pool.
        return await asyncpg.connect(
            host=self.host,
            port=self.port,
            database=self.dbname,
            user=self.username,
            password=self.password,
            timeout=self.timeout,
            ssl="require",
        )

    async def test_connection(self) -> tuple[bool, str]:
        conn: asyncpg.Connection | None = None
        try:
            conn = await self._connect()
            return True, ""
        except Exception as exc:
            return False, _readable_error(exc)
        finally:
            if conn is not None:
                await conn.close()

    async def list_tables(self) -> list[str]:
        conn: asyncpg.Connection | None = None
        try:
            conn = await self._connect()
            rows = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            return [r["table_name"] for r in rows]
        finally:
            if conn is not None:
                await conn.close()

    async def preview_table(self, table_name: str, limit: int = 20) -> dict[str, Any]:
        conn: asyncpg.Connection | None = None
        try:
            conn = await self._connect()
            col_rows = await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = $1
                ORDER BY ordinal_position
                LIMIT $2
                """,
                table_name,
                self.column_limit,
            )
            columns = [r["column_name"] for r in col_rows]
            if not columns:
                return {"columns": [], "rows": []}

            quoted_cols = ", ".join(_quote_ident(c) for c in columns)
            quoted_table = _quote_ident(table_name)
            query = f"SELECT {quoted_cols} FROM {quoted_table} LIMIT {int(limit)}"
            data_rows = await conn.fetch(query)
            rows = [
                {col: _serialize_value(record[col]) for col in columns}
                for record in data_rows
            ]
            return {"columns": columns, "rows": rows}
        except Exception as exc:
            return {"columns": [], "error": _readable_error(exc)}
        finally:
            if conn is not None:
                await conn.close()

    async def get_schema(self) -> dict[str, Any]:
        conn: asyncpg.Connection | None = None
        try:
            conn = await self._connect()
            table_rows = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            col_rows = await conn.fetch(
                """
                SELECT
                    table_name,
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    ordinal_position
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
                """
            )
            pk_rows = await conn.fetch(
                """
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    kcu.ordinal_position
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = 'public'
                  AND tc.constraint_type = 'PRIMARY KEY'
                ORDER BY tc.table_name, kcu.ordinal_position
                """
            )
            fk_rows = await conn.fetch(
                """
                SELECT
                    tc.constraint_name,
                    kcu.table_name AS from_table,
                    kcu.column_name AS from_column,
                    ccu.table_name AS to_table,
                    ccu.column_name AS to_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.table_schema = 'public'
                  AND tc.constraint_type = 'FOREIGN KEY'
                ORDER BY from_table, from_column, to_table, to_column
                """
            )

            pks_by_table: dict[str, set[str]] = {}
            for r in pk_rows:
                pks_by_table.setdefault(r["table_name"], set()).add(r["column_name"])

            fk_by_table_col: dict[tuple[str, str], str] = {}
            relationships: list[dict[str, Any]] = []
            seen_rels: set[tuple[str, str, str, str]] = set()
            for r in fk_rows:
                from_table = r["from_table"]
                from_column = r["from_column"]
                to_table = r["to_table"]
                to_column = r["to_column"]
                fk_by_table_col[(from_table, from_column)] = f"{to_table}.{to_column}"
                key = (from_table, from_column, to_table, to_column)
                if key in seen_rels:
                    continue
                seen_rels.add(key)
                relationships.append(
                    {
                        "from_table": from_table,
                        "from_column": from_column,
                        "to_table": to_table,
                        "to_column": to_column,
                        "cardinality": "many_to_one",
                        "confidence": "declared",
                    }
                )

            columns_by_table: dict[str, list[dict[str, Any]]] = {}
            for r in col_rows:
                table = r["table_name"]
                col_name = r["column_name"]
                columns_by_table.setdefault(table, []).append(
                    {
                        "name": col_name,
                        "type": r["data_type"],
                        "nullable": r["is_nullable"] == "YES",
                        "primary_key": col_name in pks_by_table.get(table, set()),
                        "foreign_key": fk_by_table_col.get((table, col_name)),
                    }
                )

            tables = []
            for r in table_rows:
                name = r["table_name"]
                tables.append(
                    {
                        "table_name": name,
                        "columns": columns_by_table.get(name, []),
                        "inferred": False,
                    }
                )

            return {"tables": tables, "relationships": relationships}
        finally:
            if conn is not None:
                await conn.close()

    async def execute_query(self, sql: str, *, max_rows: int = 1000) -> dict[str, Any]:
        query = validate_readonly_sql(sql)
        conn: asyncpg.Connection | None = None
        try:
            conn = await self._connect()
            await conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
            records = await conn.fetch(wrap_sql_row_limit(query, max_rows))

            columns = list(records[0].keys()) if records else []
            rows = [
                {col: _serialize_value(record[col]) for col in columns}
                for record in records
            ]
            return {
                "status": "ok",
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(_readable_error(exc)) from exc
        finally:
            if conn is not None:
                await conn.close()
