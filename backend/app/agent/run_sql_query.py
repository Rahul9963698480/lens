"""Agno tool to execute pre-approved SQL — LLM cannot supply or change the query."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from agno.tools import tool

from app.db.query_runner import execute_project_sql, result_to_json

DEFAULT_MAX_ROWS = 1000


def create_run_sql_query_tool(
    project_id: UUID,
    pool: asyncpg.Pool,
    approved_sql: str,
):
    """Create a no-arg tool that always runs the API-approved SQL.

    The LLM may call this tool, but it cannot pass SQL as an argument.
    Used only when an agent orchestrates execution; prefer execute_sql_for_project
    for the public API.
    """
    _project_id = project_id
    _pool = pool
    _approved_sql = approved_sql

    @tool
    async def run_sql_query() -> str:
        """Execute the pre-approved read-only SELECT for this request.

        This tool takes no arguments. The SQL was validated and bound by the
        backend before the agent run started.
        """
        try:
            payload = await execute_project_sql(
                _pool,
                _project_id,
                _approved_sql,
                max_rows=DEFAULT_MAX_ROWS,
            )
        except ValueError as exc:
            payload = {
                "status": "error",
                "message": str(exc),
                "columns": [],
                "rows": [],
                "row_count": 0,
            }
        return result_to_json(payload)

    return run_sql_query
