"""Per-process local cache of xlsx-project DuckDB files.

A project's data is immutable after upload, so this cache never invalidates
or expires. First access on a process downloads once; later queries reuse
the local file.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from app.storage.supabase_storage import download_file, upload_file

logger = logging.getLogger(__name__)

_local_cache: dict[str, str] = {}


def cache_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "xlsx_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def local_duckdb_path(project_id: str) -> Path:
    return cache_dir() / f"{project_id}.duckdb"


def seed_local_cache(project_id: str, local_path: str) -> None:
    """Register an already-built DuckDB file so the first query skips download."""
    _local_cache[project_id] = local_path
    logger.info("xlsx cache seed project_id=%s path=%s", project_id, local_path)


def evict_local_cache(project_id: str) -> None:
    """Drop the in-memory entry and delete the local file if present."""
    path = _local_cache.pop(project_id, None)
    if path is None:
        path = str(local_duckdb_path(project_id))
    for candidate in (path, str(local_duckdb_path(project_id))):
        try:
            if os.path.exists(candidate):
                os.remove(candidate)
        except OSError:
            logger.warning(
                "xlsx cache could not delete local file project_id=%s path=%s",
                project_id,
                candidate,
            )
    logger.info("xlsx cache evict project_id=%s", project_id)


async def persist_indexed_duckdb(storage_path: str, local_path: str) -> None:
    """Upload the locally indexed .duckdb file so all servers get optimized storage."""
    await upload_file(storage_path, local_path, upsert=True)


async def get_cached_local_path(project_id: str, storage_path: str) -> str:
    cached = _local_cache.get(project_id)
    if cached and os.path.exists(cached):
        logger.info("xlsx cache hit project_id=%s path=%s", project_id, cached)
        return cached

    local_path = str(local_duckdb_path(project_id))
    logger.info("xlsx cache download project_id=%s storage_path=%s", project_id, storage_path)
    await download_file(storage_path, local_path)
    _local_cache[project_id] = local_path
    return local_path
