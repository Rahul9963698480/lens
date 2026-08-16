"""Execute validated read-only SQL against a project's external database."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

from app.db import app_db
from app.db.connectors import get_connector
from app.db.connectors.postgres import PostgresConnector, _readable_error, _serialize_value
from app.db.sql_validation import validate_readonly_sql

DEFAULT_MAX_ROWS = 1000
STATEMENT_TIMEOUT_MS = 30_000


async def execute_project_sql(
    pool: asyncpg.Pool,
    project_id: UUID,
    sql: str,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> dict[str, Any]:
    """Run a read-only SQL query on the project's external Postgres database."""
    query = validate_readonly_sql(sql)

    project = await app_db.get_project_with_password(pool, project_id)
    if project is None:
        raise ValueError("Project not found.")

    if project["engine"] != "postgres":
        raise ValueError("SQL execution is only supported for postgres projects.")

    connector = get_connector(
        project["engine"],
        project["db_host"],
        project["db_port"],
        project["db_name"],
        project["db_username"],
        project["db_password"],
    )
    if not isinstance(connector, PostgresConnector):
        raise ValueError("SQL execution is only supported for postgres projects.")

    conn: asyncpg.Connection | None = None
    try:
        conn = await connector._connect()
        await conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")

        records = await conn.fetch(query)
        if len(records) > max_rows:
            records = records[:max_rows]

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


def result_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, default=str)
