"""Abstract interface for external (user-supplied) database connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DBConnector(ABC):
    """Short-lived connections only — open, use, close. Never pool."""

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Return (True, "") on success, or (False, readable_error) on failure."""

    @abstractmethod
    async def list_tables(self) -> list[str]:
        """List table names (Postgres) or collection names (MongoDB)."""

    @abstractmethod
    async def preview_table(self, table_name: str, limit: int = 20) -> dict[str, Any]:
        """
        Return {"columns": [...], "rows": [...]} or {"columns": [...], "error": "..."}.
        """

    @abstractmethod
    async def execute_query(self, sql: str, *, max_rows: int = 1000) -> dict[str, Any]:
        """
        Run a validated read-only SQL query.

        Return {"status": "ok", "columns": [...], "rows": [...], "row_count": int}.
        Raise ValueError when the engine does not support SQL execution or
        the query fails.
        """

    @abstractmethod
    async def get_schema(self) -> dict[str, Any]:
        """
        Return structure-only schema for all tables/collections:

        {
          "tables": [
            {
              "table_name": str,
              "columns": [
                # Postgres / Mongo declared:
                #   {name, type, nullable, primary_key?, foreign_key?}
                # Mongo sampled:
                #   {name, inferred_type, presence_pct}
              ],
              "inferred": bool,  # False when schema is declared
            }
          ],
          "relationships": [
            {
              "from_table": str,
              "from_column": str,
              "to_table": str,
              "to_column": str,
              "cardinality": "many_to_one" | "one_to_one" | "one_to_many" | "unknown",
              "confidence": "declared" | "inferred" | "inferred_from_data",
            }
          ],
          # Present only when any table is inferred or any relationship
          # has confidence "inferred" or "inferred_from_data":
          "note": str | None,
        }
        """
