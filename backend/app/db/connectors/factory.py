"""Factory: pick the right external DB connector from engine name."""

from __future__ import annotations

from app.db.connectors.base import DBConnector
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
