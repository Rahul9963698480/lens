"""Playground chat threads — question, SQL, and analysis answer only."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

_CONVERSATION_COLS = "id, project_id, title, created_at, updated_at"
_MESSAGE_COLS = (
    "id, conversation_id, question, sql, answer, analysis_id, queries_used, created_at"
)


def conversation_title(question: str) -> str:
    text = " ".join((question or "").split())
    if len(text) <= 48:
        return text or "New chat"
    return text[:45].rstrip() + "..."


async def create_conversation(
    pool: asyncpg.Pool,
    *,
    project_id: UUID,
    title: str,
) -> asyncpg.Record:
    return await pool.fetchrow(
        f"""
        INSERT INTO playground_conversations (project_id, title)
        VALUES ($1, $2)
        RETURNING {_CONVERSATION_COLS}
        """,
        project_id,
        title,
    )


async def list_conversations(
    pool: asyncpg.Pool,
    project_id: UUID,
) -> list[asyncpg.Record]:
    return await pool.fetch(
        f"""
        SELECT {_CONVERSATION_COLS}
        FROM playground_conversations
        WHERE project_id = $1
        ORDER BY updated_at DESC
        """,
        project_id,
    )


async def get_conversation(
    pool: asyncpg.Pool,
    project_id: UUID,
    conversation_id: UUID,
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        f"""
        SELECT {_CONVERSATION_COLS}
        FROM playground_conversations
        WHERE id = $1 AND project_id = $2
        """,
        conversation_id,
        project_id,
    )


async def list_messages(
    pool: asyncpg.Pool,
    conversation_id: UUID,
) -> list[asyncpg.Record]:
    return await pool.fetch(
        f"""
        SELECT {_MESSAGE_COLS}
        FROM playground_messages
        WHERE conversation_id = $1
        ORDER BY created_at ASC
        """,
        conversation_id,
    )


async def list_recent_turns(
    pool: asyncpg.Pool,
    conversation_id: UUID,
    *,
    limit: int = 5,
) -> list[asyncpg.Record]:
    rows = await pool.fetch(
        f"""
        SELECT {_MESSAGE_COLS}
        FROM playground_messages
        WHERE conversation_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        conversation_id,
        limit,
    )
    return list(reversed(rows))


async def insert_message(
    pool: asyncpg.Pool,
    *,
    conversation_id: UUID,
    question: str,
    sql: str,
    answer: str,
    analysis_id: UUID | None,
    queries_used: list[dict[str, Any]] | None,
) -> asyncpg.Record:
    payload = json.dumps(queries_used, default=str) if queries_used is not None else None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                f"""
                INSERT INTO playground_messages (
                    conversation_id, question, sql, answer, analysis_id, queries_used
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                RETURNING {_MESSAGE_COLS}
                """,
                conversation_id,
                question,
                sql,
                answer,
                analysis_id,
                payload,
            )
            await conn.execute(
                """
                UPDATE playground_conversations
                SET updated_at = now()
                WHERE id = $1
                """,
                conversation_id,
            )
    return row


async def delete_conversation(
    pool: asyncpg.Pool,
    project_id: UUID,
    conversation_id: UUID,
) -> bool:
    result = await pool.execute(
        """
        DELETE FROM playground_conversations
        WHERE id = $1 AND project_id = $2
        """,
        conversation_id,
        project_id,
    )
    return result == "DELETE 1"
