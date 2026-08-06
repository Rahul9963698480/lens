"""Per-table schema catalog — extract, upsert, and annotation updates."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

from app.db.connectors.base import DBConnector

COLUMN_ANNOTATION_KEYS = (
    "description",
    "business_name",
    "value_mappings",
    "null_meanings",
    "caveats",
)

_SELECT_COLS = """
    db_name, table_name, table_description, business_name,
    columns, relationships, inferred, updated_at
"""


def _parse_json(value: Any) -> Any:
    """Normalize asyncpg JSONB (already decoded) or a JSON string."""
    if isinstance(value, str):
        return json.loads(value)
    return value


def _row_to_dict(record: asyncpg.Record) -> dict[str, Any]:
    row = dict(record)
    row["columns"] = _parse_json(row["columns"])
    row["relationships"] = _parse_json(row["relationships"])
    return row


async def get_stored_schema(
    pool: asyncpg.Pool, project_id: UUID
) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        f"""
        SELECT {_SELECT_COLS}
        FROM table_schema_catalog
        WHERE project_id = $1
        ORDER BY table_name
        """,
        project_id,
    )
    return [_row_to_dict(r) for r in rows]


async def upsert_table_schema(
    pool: asyncpg.Pool,
    project_id: UUID,
    db_name: str,
    table: dict[str, Any],
    relationships: list[dict[str, Any]],
) -> None:
    existing = await pool.fetchrow(
        """
        SELECT columns FROM table_schema_catalog
        WHERE project_id = $1 AND table_name = $2
        """,
        project_id,
        table["table_name"],
    )
    if existing:
        existing_by_name = {
            c["name"]: c for c in _parse_json(existing["columns"])
        }
        for col in table["columns"]:
            prev = existing_by_name.get(col["name"])
            if not prev:
                continue
            for key in COLUMN_ANNOTATION_KEYS:
                if prev.get(key):
                    col[key] = prev[key]

    table_relationships = [
        r
        for r in relationships
        if r["from_table"] == table["table_name"]
        or r["to_table"] == table["table_name"]
    ]

    # table_description / business_name intentionally omitted from DO UPDATE
    # so re-sync never wipes user-written table-level annotations.
    await pool.execute(
        """
        INSERT INTO table_schema_catalog
            (project_id, db_name, table_name, columns, relationships, inferred, updated_at)
        VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, now())
        ON CONFLICT (project_id, table_name)
        DO UPDATE SET columns = $4::jsonb, relationships = $5::jsonb, inferred = $6,
                       db_name = $2, updated_at = now()
        """,
        project_id,
        db_name,
        table["table_name"],
        json.dumps(table["columns"]),
        json.dumps(table_relationships),
        table["inferred"],
    )


async def extract_and_store_schema(
    pool: asyncpg.Pool,
    project_id: UUID,
    db_name: str,
    connector: DBConnector,
) -> list[dict[str, Any]]:
    raw_schema = await connector.get_schema()

    for table in raw_schema["tables"]:
        for col in table["columns"]:
            for key in COLUMN_ANNOTATION_KEYS:
                col.setdefault(key, None)

    for table in raw_schema["tables"]:
        await upsert_table_schema(
            pool,
            project_id,
            db_name,
            table,
            raw_schema.get("relationships", []),
        )

    return await get_stored_schema(pool, project_id)


async def update_table_annotations(
    pool: asyncpg.Pool,
    project_id: UUID,
    table_name: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    if not updates:
        row = await pool.fetchrow(
            f"""
            SELECT {_SELECT_COLS}
            FROM table_schema_catalog
            WHERE project_id = $1 AND table_name = $2
            """,
            project_id,
            table_name,
        )
        return _row_to_dict(row) if row else None

    allowed = {"table_description", "business_name"}
    sets = []
    values: list[Any] = [project_id, table_name]
    for key, value in updates.items():
        if key not in allowed:
            continue
        values.append(value)
        sets.append(f"{key} = ${len(values)}")

    if not sets:
        return await update_table_annotations(pool, project_id, table_name, {})

    sets.append("updated_at = now()")
    row = await pool.fetchrow(
        f"""
        UPDATE table_schema_catalog
        SET {", ".join(sets)}
        WHERE project_id = $1 AND table_name = $2
        RETURNING {_SELECT_COLS}
        """,
        *values,
    )
    return _row_to_dict(row) if row else None


async def update_column_annotations(
    pool: asyncpg.Pool,
    project_id: UUID,
    table_name: str,
    column_name: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    existing = await pool.fetchrow(
        f"""
        SELECT {_SELECT_COLS}
        FROM table_schema_catalog
        WHERE project_id = $1 AND table_name = $2
        """,
        project_id,
        table_name,
    )
    if existing is None:
        return None

    columns = _parse_json(existing["columns"])
    matched = False
    for col in columns:
        if col["name"] == column_name:
            for key, value in updates.items():
                if key in COLUMN_ANNOTATION_KEYS:
                    col[key] = value
            matched = True
            break
    if not matched:
        return None

    row = await pool.fetchrow(
        f"""
        UPDATE table_schema_catalog
        SET columns = $3::jsonb, updated_at = now()
        WHERE project_id = $1 AND table_name = $2
        RETURNING {_SELECT_COLS}
        """,
        project_id,
        table_name,
        json.dumps(columns),
    )
    return _row_to_dict(row) if row else None
