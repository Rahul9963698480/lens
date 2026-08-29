"""Factory: pick the right external DB connector from engine name."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.db.connectors.base import DBConnector
from app.db.connectors.duckdb_file import DuckDBFileConnector
from app.db.connectors.mongodb import MongoDBConnector
from app.db.connectors.postgres import PostgresConnector

DEFAULT_PORTS = {
    "postgres": 5432,
    "mongodb": 27017,
}


def resolve_db_port(engine: str) -> int:
    key = (engine or "").strip().lower()
    if key not in DEFAULT_PORTS:
        raise ValueError(f"Unsupported engine: {engine}")
    return DEFAULT_PORTS[key]


def get_connector(
    engine: str,
    host: str,
    port: int,
    dbname: str,
    username: str,
    password: str,
) -> DBConnector:
    key = (engine or "").strip().lower()
    if key == "postgres":
        return PostgresConnector(host, port, dbname, username, password)
    if key == "mongodb":
        return MongoDBConnector(host, port, dbname, username, password)
    raise ValueError(f"Unsupported engine: {engine}")


def get_connector_from_project(project: Mapping[str, Any]) -> DBConnector:
    """Build a connector from a stored projects row."""
    engine = (project["engine"] or "").strip().lower()
    if engine == "xlsx":
        file_path = project["file_path"]
        if not file_path:
            raise ValueError("xlsx project is missing file_path")
        return DuckDBFileConnector(str(project["id"]), file_path)
    return get_connector(
        engine,
        project["db_host"],
        project["db_port"],
        project["db_name"],
        project["db_username"],
        project["db_password"],
    )
