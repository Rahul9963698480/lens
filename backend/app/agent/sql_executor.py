"""Execute validated read-only SQL — backend only, never via LLM tool args."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from app.db.query_runner import execute_project_sql


async def execute_sql_for_project(
    project_id: UUID,
    sql: str,
    pool: asyncpg.Pool,
) -> dict:
    """Run API-approved SQL on the project database.

  Security: SQL comes only from the API request body. The LLM is not involved
  in execution and cannot change which query runs.
    """
    payload = await execute_project_sql(pool, project_id, sql)
    if payload.get("status") == "error":
        raise ValueError(payload.get("message") or "SQL execution failed.")
    return payload
