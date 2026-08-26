"""Schema introspection from table_schema_catalog (Lens)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
from agno.tools import tool
from agno.utils.log import logger

app_logger = logging.getLogger(__name__)

CATALOG_TABLE = "table_schema_catalog"
MAX_TABLES_IN_LIST = 200
_SAFE_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _normalize_foreign_key(fk: Any) -> dict[str, str] | str | None:
    if isinstance(fk, dict):
        return {
            "table": fk.get("table") or "",
            "column": fk.get("column") or "",
        }
    if isinstance(fk, str):
        return fk
    return None


def _normalize_columns(columns: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for col in columns:
        if not isinstance(col, dict):
            continue
        normalized.append(
            {
                "name": col.get("name") or "",
                "type": col.get("type") or "",
                "nullable": bool(col.get("nullable", True)),
                "primary_key": bool(col.get("primary_key")),
                "foreign_key": _normalize_foreign_key(col.get("foreign_key")),
                "business_name": col.get("business_name") or "",
                "description": col.get("description") or "",
            }
        )
    return normalized


def _normalize_relationships(relationships: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for rel in relationships:
        if not isinstance(rel, dict):
            continue
        normalized.append(
            {
                "from_table": rel.get("from_table") or "",
                "from_column": rel.get("from_column") or "",
                "to_table": rel.get("to_table") or "",
                "to_column": rel.get("to_column") or "",
                "cardinality": rel.get("cardinality") or "unknown",
                "confidence": rel.get("confidence") or "unknown",
            }
        )
    return normalized


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, default=str)


def create_introspect_schema_tool(project_id: UUID | str, pool: asyncpg.Pool):
    """Create introspect_schema tool scoped to one project."""
    _pool = pool
    _project_id = UUID(str(project_id))

    @tool
    async def introspect_schema(
        table_name: str = "all",
        include_relationships: bool = True,
    ) -> str:
        """Read schema metadata from table_schema_catalog.

        Use a specific table name for SQL generation (e.g. "customer", "store").
        Use table_name="all" ONLY for discovery when you cannot infer which tables exist.

        `all` returns table names and column name previews only — not full schema.
        Always introspect each required table by name before writing SQL.

        Args:
            table_name: One table name, or "all" for a lightweight catalog listing.
            include_relationships: Include relationships when describing one table.
        """
        requested = (table_name or "all").strip()
        list_all = requested.lower() in {"all", "*", "none", ""}
        stamp = datetime.now(timezone.utc).isoformat()
        logger.info(
            f"introspect_schema called: project_id={_project_id} "
            f"table_name={requested!r} timestamp={stamp}"
        )
        app_logger.info(
            "introspect_schema called project_id=%s table_name=%s timestamp=%s",
            _project_id,
            requested,
            stamp,
        )

        if not list_all and not _SAFE_TABLE_NAME.match(requested):
            return _json_response(
                {
                    "status": "error",
                    "error_type": "invalid_table_name",
                    "message": "Table name contains invalid characters.",
                }
            )

        try:
            if list_all:
                rows = await _pool.fetch(
                    f"""
                    SELECT table_name, db_name, business_name, table_description,
                           columns, updated_at
                    FROM {CATALOG_TABLE}
                    WHERE project_id = $1
                    ORDER BY table_name
                    LIMIT $2
                    """,
                    _project_id,
                    MAX_TABLES_IN_LIST,
                )

                if not rows:
                    return _json_response(
                        {
                            "status": "empty",
                            "project_id": str(_project_id),
                            "source": CATALOG_TABLE,
                            "message": f"No tables found in {CATALOG_TABLE} for project_id={_project_id}.",
                            "tables": [],
                        }
                    )

                tables = []
                for row in rows:
                    col_names = [
                        c.get("name")
                        for c in _as_list(row["columns"])
                        if isinstance(c, dict) and c.get("name")
                    ]
                    tables.append(
                        {
                            "table_name": row["table_name"],
                            "db_name": row.get("db_name"),
                            "business_name": row.get("business_name"),
                            "table_description": row.get("table_description"),
                            "columns_preview": col_names,
                            "updated_at": row.get("updated_at"),
                        }
                    )

                return _json_response(
                    {
                        "status": "ok",
                        "project_id": str(_project_id),
                        "source": CATALOG_TABLE,
                        "table_count": len(tables),
                        "tables": tables,
                    }
                )

            row = await _pool.fetchrow(
                f"""
                SELECT project_id, db_name, table_name, columns, relationships,
                       inferred, updated_at, table_description, business_name
                FROM {CATALOG_TABLE}
                WHERE project_id = $1
                  AND table_name = $2
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 1
                """,
                _project_id,
                requested,
            )

            if row is None:
                available_rows = await _pool.fetch(
                    f"""
                    SELECT table_name FROM {CATALOG_TABLE}
                    WHERE project_id = $1
                    ORDER BY 1 LIMIT 50
                    """,
                    _project_id,
                )
                return _json_response(
                    {
                        "status": "not_found",
                        "project_id": str(_project_id),
                        "source": CATALOG_TABLE,
                        "requested_table": requested,
                        "message": f"Table '{requested}' not found in {CATALOG_TABLE}.",
                        "available_tables_sample": [r["table_name"] for r in available_rows],
                    }
                )

            columns = _normalize_columns(_as_list(row["columns"]))
            relationships = (
                _normalize_relationships(_as_list(row["relationships"]))
                if include_relationships
                else []
            )

            table: dict[str, Any] = {
                "table_name": row["table_name"],
                "business_name": row.get("business_name"),
                "db_name": row.get("db_name"),
                "table_description": row.get("table_description"),
                "inferred": row.get("inferred"),
                "updated_at": row.get("updated_at"),
                "columns": columns,
                "relationships": relationships,
            }
            if any(r.get("confidence") == "inferred_from_data" for r in relationships):
                table["note"] = (
                    "Some relationships were inferred from overlapping column values "
                    "(confidence=inferred_from_data), not declared foreign keys."
                )
            elif include_relationships and not relationships:
                table["note"] = (
                    "No relationships are declared for this table. "
                    "Do not join it to another table."
                )

            return _json_response(
                {
                    "status": "ok",
                    "project_id": row.get("project_id"),
                    "source": CATALOG_TABLE,
                    "table": table,
                }
            )

        except (asyncpg.PostgresConnectionError, OSError) as e:
            logger.error(f"Catalog DB connection failed: {e}")
            return _json_response(
                {
                    "status": "error",
                    "error_type": "connection",
                    "message": "Could not connect to the schema catalog database.",
                }
            )
        except asyncpg.PostgresError as e:
            logger.error(f"Catalog query failed: {e}")
            return _json_response(
                {
                    "status": "error",
                    "error_type": "query",
                    "message": "Failed to read table_schema_catalog.",
                }
            )

    return introspect_schema
