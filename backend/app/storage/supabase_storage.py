"""Supabase Storage helpers for durable xlsx-project DuckDB files."""

from __future__ import annotations

import asyncio
from pathlib import Path

from supabase import Client, create_client

from app.config import settings

_DUCKDB_CONTENT_TYPE = "application/octet-stream"


class StorageConfigError(RuntimeError):
    """Raised when Storage credentials are missing."""


def parse_storage_path(storage_path: str) -> tuple[str, str]:
    """Split `{bucket}/{object_key}` into bucket name and object key."""
    text = (storage_path or "").strip()
    if "/" not in text:
        raise ValueError(f"Invalid storage path: {storage_path!r}")
    bucket, key = text.split("/", 1)
    if not bucket or not key:
        raise ValueError(f"Invalid storage path: {storage_path!r}")
    return bucket, key


def storage_object_path(project_id: str) -> str:
    """Return the canonical `file_path` stored on the projects row."""
    return f"{settings.SUPABASE_STORAGE_BUCKET}/{project_id}.duckdb"


def _require_storage_settings() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise StorageConfigError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for xlsx storage."
        )


def _client() -> Client:
    _require_storage_settings()
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def _upload_sync(storage_path: str, local_path: str, *, upsert: bool = False) -> None:
    bucket, key = parse_storage_path(storage_path)
    data = Path(local_path).read_bytes()
    _client().storage.from_(bucket).upload(
        key,
        data,
        file_options={
            "content-type": _DUCKDB_CONTENT_TYPE,
            "upsert": "true" if upsert else "false",
        },
    )


def _download_sync(storage_path: str, local_path: str) -> None:
    bucket, key = parse_storage_path(storage_path)
    data = _client().storage.from_(bucket).download(key)
    dest = Path(local_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def _delete_sync(storage_path: str) -> None:
    bucket, key = parse_storage_path(storage_path)
    _client().storage.from_(bucket).remove([key])


async def upload_file(storage_path: str, local_path: str, *, upsert: bool = False) -> None:
    await asyncio.to_thread(_upload_sync, storage_path, local_path, upsert=upsert)


async def download_file(storage_path: str, local_path: str) -> None:
    await asyncio.to_thread(_download_sync, storage_path, local_path)


async def delete_file(storage_path: str) -> None:
    await asyncio.to_thread(_delete_sync, storage_path)
