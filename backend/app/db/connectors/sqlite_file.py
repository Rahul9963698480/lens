"""SQLite file connector for xlsx projects — local cached file, no per-query network."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import aiosqlite

from app.db.connectors.base import DBConnector
from app.db.sql_validation import validate_readonly_sql
from app.storage.xlsx_cache import get_cached_local_path
from app.storage.xlsx_relationships import (
    infer_relationship_candidates_from_path,
    merge_with_declared,
    verify_relationship_candidates,
)

RelationshipVerifier = Callable[[dict[str, Any]], bool | Awaitable[bool]]

QUERY_TIMEOUT_SECONDS = 30.0


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


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


class SQLiteFileConnector(DBConnector):
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

    async def _get_local_path(self) -> str:
        return await get_cached_local_path(self.project_id, self.storage_path)

    async def test_connection(self) -> tuple[bool, str]:
        try:
            path = await self._get_local_path()
            async with aiosqlite.connect(path) as db:
                await db.execute("SELECT 1")
            return True, ""
        except Exception as exc:
            return False, f"Could not access project data: {exc}"

    async def list_tables(self) -> list[str]:
        path = await self._get_local_path()
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
            rows = await cursor.fetchall()
            return [r["name"] for r in rows]

    async def preview_table(self, table_name: str, limit: int = 20) -> dict[str, Any]:
        try:
            tables = await self.list_tables()
            if table_name not in tables:
                return {"columns": [], "error": f"Table {table_name!r} not found."}

            path = await self._get_local_path()
            async with aiosqlite.connect(path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    f"SELECT * FROM {_quote_ident(table_name)} LIMIT {int(limit)}"
                )
                records = await cursor.fetchall()
                columns = list(records[0].keys()) if records else []
                if not columns:
                    info = await db.execute(f"PRAGMA table_info({_quote_ident(table_name)})")
                    info_rows = await info.fetchall()
                    columns = [r["name"] for r in info_rows]
                rows = [
                    {col: _serialize_value(record[col]) for col in columns}
                    for record in records
                ]
                return {"columns": columns, "rows": rows}
        except Exception as exc:
            return {"columns": [], "error": str(exc)}

    async def get_schema(self) -> dict[str, Any]:
        path = await self._get_local_path()
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            table_names = await self._table_names(db)

            relationships: list[dict[str, Any]] = []
            tables: list[dict[str, Any]] = []
            for table_name in table_names:
                info = await db.execute(f"PRAGMA table_info({_quote_ident(table_name)})")
                col_rows = await info.fetchall()
                fk = await db.execute(f"PRAGMA foreign_key_list({_quote_ident(table_name)})")
                fk_rows = await fk.fetchall()

                fk_by_col: dict[str, str] = {}
                for r in fk_rows:
                    from_col = r["from"]
                    to_table = r["table"]
                    to_col = r["to"]
                    fk_by_col[from_col] = f"{to_table}.{to_col}"
                    relationships.append(
                        {
                            "from_table": table_name,
                            "from_column": from_col,
                            "to_table": to_table,
                            "to_column": to_col,
                            "cardinality": "many_to_one",
                            "confidence": "declared",
                        }
                    )

                columns = []
                for r in col_rows:
                    col_name = r["name"]
                    columns.append(
                        {
                            "name": col_name,
                            "type": r["type"] or "TEXT",
                            "nullable": not bool(r["notnull"]),
                            "primary_key": bool(r["pk"]),
                            "foreign_key": fk_by_col.get(col_name),
                        }
                    )
                tables.append(
                    {
                        "table_name": table_name,
                        "columns": columns,
                        "inferred": True,
                    }
                )

        candidates = await asyncio.to_thread(
            infer_relationship_candidates_from_path, path, table_names
        )
        inferred = await verify_relationship_candidates(
            candidates,
            verifier=self.relationship_verifier,
        )
        return {
            "tables": tables,
            "relationships": merge_with_declared(relationships, inferred),
        }

    async def execute_query(self, sql: str, *, max_rows: int = 1000) -> dict[str, Any]:
        query = validate_readonly_sql(sql)
        path = await self._get_local_path()

        async def _run() -> dict[str, Any]:
            async with aiosqlite.connect(path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(query)
                records = await cursor.fetchmany(max_rows)
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

        try:
            return await asyncio.wait_for(_run(), timeout=QUERY_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            raise ValueError("Query timed out.") from exc
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Could not execute query: {exc}") from exc

    async def _table_names(self, db: aiosqlite.Connection) -> list[str]:
        cursor = await db.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
        rows = await cursor.fetchall()
        return [r["name"] for r in rows]
