"""Execute validated read-only SQL against a project's database."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

from app.db import app_db
from app.db.connectors import get_connector_from_project
from app.db.sql_validation import validate_readonly_sql

DEFAULT_MAX_ROWS = 1000


async def execute_project_sql(
    pool: asyncpg.Pool,
    project_id: UUID,
    sql: str,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> dict[str, Any]:
    """Run a read-only SQL query on the project's database via its connector."""
    query = validate_readonly_sql(sql)

    project = await app_db.get_project_with_password(pool, project_id)
    if project is None:
        raise ValueError("Project not found.")

    connector = get_connector_from_project(project)
    return await connector.execute_query(query, max_rows=max_rows)
