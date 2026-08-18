"""App DB (Supabase) — persistent asyncpg pool for projects only."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import Request


async def create_pool(dsn: str) -> asyncpg.Pool:
    # Supabase (and its pooler) require TLS
    # statement_cache_size=0: required for PgBouncer transaction-mode pooling
    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=10,
        ssl="require",
        statement_cache_size=0,
    )


async def close_pool(pool: asyncpg.Pool) -> None:
    await pool.close()


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


async def create_project(
    pool: asyncpg.Pool,
    *,
    name: str,
    engine: str,
    db_host: str,
    db_port: int,
    db_name: str,
    db_username: str,
    db_password: str,
) -> asyncpg.Record:
    # TODO: encrypt db_password at rest before production
    return await pool.fetchrow(
        """
        INSERT INTO projects (
            name, engine, db_host, db_port, db_name, db_username, db_password
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, name, engine, db_host, db_port, db_name, db_username,
                  status, created_at
        """,
        name,
        engine,
        db_host,
        db_port,
        db_name,
        db_username,
        db_password,
    )


async def list_projects(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT id, name, engine, db_host, db_port, db_name, db_username,
               status, created_at
        FROM projects
        ORDER BY created_at DESC
        """
    )


async def get_project(pool: asyncpg.Pool, project_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        SELECT id, name, engine, db_host, db_port, db_name, db_username,
               status, created_at
        FROM projects
        WHERE id = $1
        """,
        project_id,
    )


async def get_project_with_password(
    pool: asyncpg.Pool, project_id: UUID
) -> asyncpg.Record | None:
    """Internal use only — includes db_password for external connections."""
    return await pool.fetchrow(
        """
        SELECT id, name, engine, db_host, db_port, db_name, db_username,
               db_password, status, created_at
        FROM projects
        WHERE id = $1
        """,
        project_id,
    )


async def get_project_by_name(
    pool: asyncpg.Pool, name: str
) -> asyncpg.Record | None:
    """Look up a project by its unique name."""
    return await pool.fetchrow(
        """
        SELECT id, name, engine, db_host, db_port, db_name, db_username,
               status, created_at
        FROM projects
        WHERE name = $1
        """,
        name,
    )


async def delete_project(pool: asyncpg.Pool, project_id: UUID) -> bool:
    result = await pool.execute("DELETE FROM projects WHERE id = $1", project_id)
    return result == "DELETE 1"


def record_to_dict(record: asyncpg.Record) -> dict[str, Any]:
    return dict(record)
