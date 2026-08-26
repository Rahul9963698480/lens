"""Query attempts and confirmed learnings — app DB persistence."""

from __future__ import annotations

from uuid import UUID

import asyncpg

_ATTEMPT_COLS = """
    id, project_id, question, generated_sql, executed_sql,
    execution_status, result_row_count, feedback, created_at, analysis_id
"""

_LEARNING_COLS = """
    id, project_id, question, confirmed_sql, rule_text,
    source_attempt_id, confirmed_at, active
"""


async def get_relevant_learnings(
    pool: asyncpg.Pool,
    project_id: UUID,
    question: str,
    limit: int = 5,
) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT question, confirmed_sql, rule_text FROM confirmed_learnings
        WHERE project_id = $1 AND active = true
        AND to_tsvector('english', search_text) @@
            replace(plainto_tsquery('english', $2)::text, ' & ', ' | ')::tsquery
        LIMIT $3
        """,
        project_id,
        question,
        limit,
    )


async def insert_query_attempt(
    pool: asyncpg.Pool,
    *,
    project_id: UUID,
    question: str,
    generated_sql: str,
    analysis_id: UUID | None = None,
) -> asyncpg.Record:
    return await pool.fetchrow(
        f"""
        INSERT INTO query_attempts (
            project_id, question, generated_sql, feedback, execution_status, analysis_id
        )
        VALUES ($1, $2, $3, 'unknown', 'not_run', $4)
        RETURNING {_ATTEMPT_COLS}
        """,
        project_id,
        question,
        generated_sql,
        analysis_id,
    )


async def list_attempts_for_analysis(
    pool: asyncpg.Pool,
    project_id: UUID,
    analysis_id: UUID,
) -> list[asyncpg.Record]:
    return await pool.fetch(
        f"""
        SELECT {_ATTEMPT_COLS}
        FROM query_attempts
        WHERE project_id = $1 AND analysis_id = $2
        ORDER BY created_at ASC
        """,
        project_id,
        analysis_id,
    )


async def get_query_attempt(
    pool: asyncpg.Pool,
    project_id: UUID,
    attempt_id: UUID,
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        f"""
        SELECT {_ATTEMPT_COLS}
        FROM query_attempts
        WHERE id = $1 AND project_id = $2
        """,
        attempt_id,
        project_id,
    )


async def update_attempt_execution(
    pool: asyncpg.Pool,
    project_id: UUID,
    attempt_id: UUID,
    *,
    executed_sql: str,
    execution_status: str,
    result_row_count: int | None,
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        f"""
        UPDATE query_attempts
        SET executed_sql = $3,
            execution_status = $4,
            result_row_count = $5
        WHERE id = $1 AND project_id = $2
        RETURNING {_ATTEMPT_COLS}
        """,
        attempt_id,
        project_id,
        executed_sql,
        execution_status,
        result_row_count,
    )


async def update_attempt_feedback(
    pool: asyncpg.Pool,
    project_id: UUID,
    attempt_id: UUID,
    feedback: str,
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        f"""
        UPDATE query_attempts
        SET feedback = $3
        WHERE id = $1 AND project_id = $2
        RETURNING {_ATTEMPT_COLS}
        """,
        attempt_id,
        project_id,
        feedback,
    )


async def insert_confirmed_learning(
    pool: asyncpg.Pool,
    *,
    project_id: UUID,
    question: str,
    confirmed_sql: str,
    rule_text: str | None,
    source_attempt_id: UUID,
) -> asyncpg.Record:
    return await pool.fetchrow(
        f"""
        INSERT INTO confirmed_learnings (
            project_id, question, confirmed_sql, rule_text, source_attempt_id
        )
        VALUES ($1, $2, $3, $4, $5)
        RETURNING {_LEARNING_COLS}
        """,
        project_id,
        question,
        confirmed_sql,
        rule_text,
        source_attempt_id,
    )
