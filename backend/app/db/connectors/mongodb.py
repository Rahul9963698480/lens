"""MongoDB external connector — short-lived Motor clients only."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import quote_plus

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from app.db.connectors.base import DBConnector


def _is_atlas_host(host: str) -> bool:
    h = host.lower()
    return h.endswith("mongodb.net") or ".mongodb." in h


def build_mongo_uri(
    host: str,
    port: int,
    dbname: str,
    username: str,
    password: str,
) -> str:
    user = quote_plus(username)
    pwd = quote_plus(password)
    if _is_atlas_host(host):
        return (
            f"mongodb+srv://{user}:{pwd}@{host}/{dbname}"
            f"?retryWrites=true&w=majority"
        )
    return f"mongodb://{user}:{pwd}@{host}:{port}/{dbname}"


def _readable_error(exc: BaseException) -> str:
    msg = str(exc).lower()

    if "authentication failed" in msg or "bad auth" in msg or "auth failed" in msg:
        return "Authentication failed - check the username and password."
    if "timed out" in msg or "timeout" in msg:
        return "Connection timed out - check the host and that the database is reachable."
    if "name or service not known" in msg or "nodename nor servname" in msg:
        return "Host unreachable - check the hostname."
    if "connection refused" in msg:
        return "Connection refused - check the host and port."
    if "server selection timeout" in msg:
        return "Could not reach the MongoDB cluster - check the host and network access."
    if "ssl" in msg or "tls" in msg:
        return "TLS/SSL connection failed - check the host and certificate settings."

    return "Could not connect to the database - check the connection details."


def _serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    return value


def _infer_type(value: Any) -> str:
    if isinstance(value, ObjectId):
        return "objectid"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if isinstance(value, bytes):
        return "bytes"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__.lower()


def _ref_stem(field_name: str) -> str | None:
    """Extract a reference stem from movie_id / movieId / movies_id style fields."""
    if field_name == "_id":
        return None
    if field_name.endswith("_id") and len(field_name) > 3:
        return field_name[:-3]
    if field_name.endswith("Id") and len(field_name) > 2 and field_name[-3].islower():
        return field_name[:-2]
    return None


def _plural_candidates(stem: str) -> list[str]:
    s = stem.lower()
    out = [s, f"{s}s", f"{s}es"]
    if s.endswith("y") and len(s) > 1 and s[-2] not in "aeiou":
        out.append(f"{s[:-1]}ies")
    seen: set[str] = set()
    ordered: list[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _resolve_target_collection(field_name: str, collections: set[str]) -> str | None:
    stem = _ref_stem(field_name)
    if stem is None:
        return None

    # Prefer exact case-insensitive match against known collections.
    by_lower = {c.lower(): c for c in collections}
    for candidate in _plural_candidates(stem):
        if candidate in by_lower:
            return by_lower[candidate]

    # Also try the raw stem as embedded in names (e.g. movie -> embedded_movies skipped;
    # only exact pluralization above to avoid noisy false positives).
    return None


def _column_type(col: dict[str, Any]) -> str | None:
    """Return the declared or inferred type string for a column dict."""
    return col.get("inferred_type") or col.get("type")


def _id_type_by_collection(tables: list[dict[str, Any]]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for table in tables:
        id_type: str | None = None
        for col in table.get("columns", []):
            if col.get("name") == "_id":
                id_type = _column_type(col)
                break
        out[table["table_name"]] = id_type
    return out


def _bson_type_to_str(bson_type: Any) -> str:
    if isinstance(bson_type, list):
        # Prefer the first non-null type from a union like ["string", "null"].
        for item in bson_type:
            if item not in (None, "null"):
                return str(item).lower()
        return "null"
    if bson_type is None:
        return "null"
    return str(bson_type).lower()


def _columns_from_json_schema(schema: dict[str, Any]) -> list[dict[str, Any]]:
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    columns: list[dict[str, Any]] = []
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            prop = {}
        bson_type = prop.get("bsonType", prop.get("type"))
        columns.append(
            {
                "name": str(name),
                "type": _bson_type_to_str(bson_type),
                "nullable": str(name) not in required,
            }
        )
    return columns


def _infer_relationships(
    tables: list[dict[str, Any]],
    collection_names: list[str],
) -> list[dict[str, Any]]:
    collections = set(collection_names)
    id_types = _id_type_by_collection(tables)
    relationships: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for table in tables:
        from_table = table["table_name"]
        table_inferred = bool(table.get("inferred"))
        for col in table.get("columns", []):
            from_column = col["name"]
            to_table = _resolve_target_collection(from_column, collections)
            if to_table is None:
                continue

            # Sampled fields need high presence; validator fields are treated as present.
            if table_inferred:
                presence_pct = col.get("presence_pct")
                if presence_pct is None or presence_pct <= 50.0:
                    continue

            col_type = _column_type(col)
            target_id_type = id_types.get(to_table)
            if col_type != "objectid" and not (
                col_type is not None
                and target_id_type is not None
                and col_type == target_id_type
            ):
                continue

            to_column = "_id"
            key = (from_table, from_column, to_table, to_column)
            if key in seen:
                continue
            seen.add(key)
            relationships.append(
                {
                    "from_table": from_table,
                    "from_column": from_column,
                    "to_table": to_table,
                    "to_column": to_column,
                    "cardinality": "many_to_one",
                    "confidence": "inferred",
                }
            )
    return relationships


class MongoDBConnector(DBConnector):
    def __init__(
        self,
        host: str,
        port: int,
        dbname: str,
        username: str,
        password: str,
        *,
        timeout_ms: int = 5000,
        column_limit: int = 5,
    ) -> None:
        self.host = host
        self.port = port
        self.dbname = dbname
        self.username = username
        self.password = password
        self.timeout_ms = timeout_ms
        self.column_limit = column_limit
        self.uri = build_mongo_uri(host, port, dbname, username, password)

    def _client(self) -> AsyncIOMotorClient:
        return AsyncIOMotorClient(
            self.uri,
            serverSelectionTimeoutMS=self.timeout_ms,
            connectTimeoutMS=self.timeout_ms,
        )

    async def test_connection(self) -> tuple[bool, str]:
        client: AsyncIOMotorClient | None = None
        try:
            client = self._client()
            await client.admin.command("ping")
            return True, ""
        except Exception as exc:
            return False, _readable_error(exc)
        finally:
            if client is not None:
                client.close()

    async def list_tables(self) -> list[str]:
        client: AsyncIOMotorClient | None = None
        try:
            client = self._client()
            names = await client[self.dbname].list_collection_names()
            return sorted(names)
        finally:
            if client is not None:
                client.close()

    async def preview_table(self, table_name: str, limit: int = 20) -> dict[str, Any]:
        client: AsyncIOMotorClient | None = None
        try:
            client = self._client()
            cursor = client[self.dbname][table_name].find().limit(int(limit))
            docs = await cursor.to_list(length=int(limit))

            columns: list[str] = []
            seen: set[str] = set()
            for doc in docs:
                for key in doc.keys():
                    if key not in seen:
                        seen.add(key)
                        columns.append(str(key))
                        if len(columns) >= self.column_limit:
                            break
                if len(columns) >= self.column_limit:
                    break

            rows = [
                {col: _serialize_value(doc.get(col)) for col in columns}
                for doc in docs
            ]
            return {"columns": columns, "rows": rows}
        except Exception as exc:
            return {"columns": [], "error": _readable_error(exc)}
        finally:
            if client is not None:
                client.close()

    async def _json_schema_validator(
        self, db: Any, collection_name: str
    ) -> dict[str, Any] | None:
        cursor = await db.list_collections(filter={"name": collection_name})
        infos = await cursor.to_list(length=1)
        if not infos:
            return None
        options = infos[0].get("options") or {}
        validator = options.get("validator") or {}
        schema = validator.get("$jsonSchema")
        return schema if isinstance(schema, dict) else None

    async def _schema_from_sample(
        self, db: Any, collection_name: str
    ) -> list[dict[str, Any]]:
        coll = db[collection_name]
        try:
            count = int(await coll.estimated_document_count())
        except Exception:
            count = int(await coll.count_documents({}))

        sample_size = min(count, 1000) if count > 0 else 0
        if sample_size == 0:
            return []

        cursor = coll.find().limit(sample_size)
        docs = await cursor.to_list(length=sample_size)
        if not docs:
            return []

        field_order: list[str] = []
        seen: set[str] = set()
        inferred_types: dict[str, str] = {}
        presence_counts: dict[str, int] = {}

        for doc in docs:
            for key, value in doc.items():
                key_str = str(key)
                if key_str not in seen:
                    seen.add(key_str)
                    field_order.append(key_str)
                presence_counts[key_str] = presence_counts.get(key_str, 0) + 1
                if key_str not in inferred_types and value is not None:
                    inferred_types[key_str] = _infer_type(value)

        n = len(docs)
        columns: list[dict[str, Any]] = []
        for key_str in field_order:
            presence_pct = round(100.0 * presence_counts.get(key_str, 0) / n, 1)
            columns.append(
                {
                    "name": key_str,
                    "inferred_type": inferred_types.get(key_str, "null"),
                    "presence_pct": presence_pct,
                }
            )
        return columns

    async def get_schema(self) -> dict[str, Any]:
        client: AsyncIOMotorClient | None = None
        try:
            client = self._client()
            db = client[self.dbname]
            collection_names = sorted(await db.list_collection_names())

            tables: list[dict[str, Any]] = []
            for name in collection_names:
                json_schema = await self._json_schema_validator(db, name)
                if json_schema is not None:
                    tables.append(
                        {
                            "table_name": name,
                            "columns": _columns_from_json_schema(json_schema),
                            "inferred": False,
                        }
                    )
                    continue

                columns = await self._schema_from_sample(db, name)
                tables.append(
                    {
                        "table_name": name,
                        "columns": columns,
                        "inferred": True,
                    }
                )

            relationships = _infer_relationships(tables, collection_names)
            result: dict[str, Any] = {
                "tables": tables,
                "relationships": relationships,
            }
            any_inferred_table = any(t.get("inferred") for t in tables)
            any_inferred_rel = any(
                r.get("confidence") == "inferred" for r in relationships
            )
            if any_inferred_table or any_inferred_rel:
                result["note"] = (
                    "Some fields are inferred from a data sample and are not "
                    "guaranteed."
                )
            return result
        finally:
            if client is not None:
                client.close()
