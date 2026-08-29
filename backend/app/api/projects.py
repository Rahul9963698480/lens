import asyncio
import logging
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from asyncpg import Pool
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.db import app_db, schema_catalog
from app.db.app_db import get_pool
from app.db.connectors import get_connector, get_connector_from_project, resolve_db_port
from app.db.connectors.duckdb_file import DuckDBFileConnector
from app.schemas.project import (
    CatalogTableSchema,
    ColumnAnnotationUpdate,
    ProjectCreate,
    ProjectPreviewResponse,
    ProjectResponse,
    ProjectSchemaResponse,
    TableAnnotationUpdate,
)
from app.storage.supabase_storage import delete_file, storage_object_path
from app.storage.xlsx_cache import (
    evict_local_cache,
    local_duckdb_path,
    persist_indexed_duckdb,
    seed_local_cache,
)
from app.storage.xlsx_ingest import XlsxIngestError, workbook_to_duckdb

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


def _catalog_response(project_id: UUID, rows: list[dict]) -> ProjectSchemaResponse:
    return ProjectSchemaResponse(
        project_id=project_id,
        db_name=rows[0]["db_name"],
        tables=[CatalogTableSchema(**row) for row in rows],
    )


async def _cleanup_xlsx_artifacts(
    *,
    pool: Pool,
    project_id: UUID,
    storage_path: str,
    duckdb_path: Path,
    row_created: bool,
    uploaded: bool,
) -> None:
    if row_created:
        try:
            await app_db.delete_project(pool, project_id)
        except Exception:
            logger.warning("Failed to delete xlsx project row %s during cleanup", project_id)
    if uploaded:
        try:
            await delete_file(storage_path)
        except Exception:
            logger.warning("Failed to delete storage object %s during cleanup", storage_path)
    try:
        evict_local_cache(str(project_id))
    except Exception:
        logger.warning("Failed to evict local cache for %s during cleanup", project_id)
    try:
        if duckdb_path.exists():
            duckdb_path.unlink()
    except OSError:
        logger.warning("Failed to delete local duckdb %s during cleanup", duckdb_path)


async def _cleanup_xlsx_on_delete(engine: str, file_path: str | None, project_id: UUID) -> None:
    if engine != "xlsx" or not file_path:
        return
    try:
        await delete_file(file_path)
    except Exception:
        logger.warning(
            "xlsx storage object already missing or delete failed: %s",
            file_path,
        )
    try:
        evict_local_cache(str(project_id))
    except Exception:
        logger.warning("xlsx local cache cleanup failed for project %s", project_id)


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    pool: Pool = Depends(get_pool),
):
    # TODO: add auth back
    try:
        db_port = resolve_db_port(payload.engine)
        connector = get_connector(
            payload.engine,
            payload.db_host,
            db_port,
            payload.db_name,
            payload.db_username,
            payload.db_password,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(exc)},
        )

    ok, message = await connector.test_connection()
    if not ok:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": message},
        )

    row = await app_db.create_project(
        pool,
        name=payload.name,
        engine=payload.engine,
        db_host=payload.db_host,
        db_port=db_port,
        db_name=payload.db_name,
        db_username=payload.db_username,
        db_password=payload.db_password,
    )

    try:
        await schema_catalog.extract_and_store_schema(
            pool, row["id"], row["db_name"], connector
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Project was created but schema sync failed. "
                "Retry with POST /projects/{id}/schema/sync."
            ),
        ) from None

    return ProjectResponse(**app_db.record_to_dict(row))


@router.post(
    "/projects/upload-xlsx",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_xlsx_project(
    file: UploadFile = File(...),
    name: str = Form(...),
    user_id: str | None = Form(None),
    pool: Pool = Depends(get_pool),
):
    # user_id is accepted for client compatibility; auth/users were removed.
    _ = user_id
    filename = file.filename or "workbook.xlsx"
    if not filename.lower().endswith(".xlsx"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Only .xlsx files are supported."},
        )

    project_id = uuid4()
    storage_path = storage_object_path(str(project_id))
    duckdb_path = local_duckdb_path(str(project_id))
    uploaded = False
    row_created = False
    xlsx_tmp: Path | None = None

    try:
        content = await file.read()
        if not content:
            raise XlsxIngestError("Uploaded file is empty.")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(content)
            xlsx_tmp = Path(tmp.name)

        workbook_to_duckdb(xlsx_tmp, duckdb_path)
        seed_local_cache(str(project_id), str(duckdb_path))

        row = await app_db.create_project(
            pool,
            name=name,
            engine="xlsx",
            db_host=None,
            db_port=None,
            db_name=filename,
            db_username=None,
            db_password=None,
            file_path=storage_path,
            project_id=project_id,
        )
        row_created = True

        connector = DuckDBFileConnector(str(project_id), storage_path)
        await schema_catalog.extract_and_store_schema(
            pool, row["id"], row["db_name"], connector
        )
        await persist_indexed_duckdb(storage_path, str(duckdb_path))
        uploaded = True
        return ProjectResponse(**app_db.record_to_dict(row))
    except XlsxIngestError as exc:
        await _cleanup_xlsx_artifacts(
            pool=pool,
            project_id=project_id,
            storage_path=storage_path,
            duckdb_path=duckdb_path,
            row_created=row_created,
            uploaded=uploaded,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(exc)},
        )
    except Exception:
        await _cleanup_xlsx_artifacts(
            pool=pool,
            project_id=project_id,
            storage_path=storage_path,
            duckdb_path=duckdb_path,
            row_created=row_created,
            uploaded=uploaded,
        )
        logger.exception("xlsx upload failed for project %s", project_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to store or sync the spreadsheet project.",
        ) from None
    finally:
        if xlsx_tmp is not None:
            try:
                xlsx_tmp.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to delete temp xlsx %s", xlsx_tmp)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    pool: Pool = Depends(get_pool),
) -> list[ProjectResponse]:
    rows = await app_db.list_projects(pool)
    return [ProjectResponse(**app_db.record_to_dict(r)) for r in rows]


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    pool: Pool = Depends(get_pool),
) -> None:
    project = await app_db.get_project(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    deleted = await app_db.delete_project(pool, project_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    await _cleanup_xlsx_on_delete(project["engine"], project["file_path"], project_id)


@router.get(
    "/projects/{project_id}/preview",
    response_model=ProjectPreviewResponse,
    response_model_exclude_none=True,
)
async def preview_project(
    project_id: UUID,
    pool: Pool = Depends(get_pool),
) -> ProjectPreviewResponse:
    project = await app_db.get_project_with_password(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        connector = get_connector_from_project(project)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None

    try:
        table_names = await connector.list_tables()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to the project's external database.",
        ) from None

    preview_limit = 5

    async def _preview_one(table_name: str) -> dict:
        result = await connector.preview_table(table_name, limit=preview_limit)
        entry: dict = {"table_name": table_name, "columns": result.get("columns", [])}
        if "error" in result:
            entry["error"] = result["error"]
        else:
            entry["rows"] = result.get("rows", [])
        return entry

    tables = list(await asyncio.gather(*(_preview_one(name) for name in table_names)))

    return ProjectPreviewResponse(project_id=project_id, tables=tables)


@router.post(
    "/projects/{project_id}/schema/sync",
    response_model=ProjectSchemaResponse,
)
async def sync_project_schema(
    project_id: UUID,
    pool: Pool = Depends(get_pool),
) -> ProjectSchemaResponse:
    project = await app_db.get_project_with_password(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        connector = get_connector_from_project(project)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None

    try:
        rows = await schema_catalog.extract_and_store_schema(
            pool, project_id, project["db_name"], connector
        )
        if (project["engine"] or "").strip().lower() == "xlsx" and project.get("file_path"):
            duckdb_path = local_duckdb_path(str(project_id))
            if duckdb_path.exists():
                await persist_indexed_duckdb(project["file_path"], str(duckdb_path))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to the project's external database.",
        ) from None

    if not rows:
        return ProjectSchemaResponse(
            project_id=project_id,
            db_name=project["db_name"],
            tables=[],
        )

    return _catalog_response(project_id, rows)


@router.get(
    "/projects/{project_id}/schema",
    response_model=ProjectSchemaResponse,
)
async def get_project_schema(
    project_id: UUID,
    pool: Pool = Depends(get_pool),
) -> ProjectSchemaResponse:
    project = await app_db.get_project(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    rows = await schema_catalog.get_stored_schema(pool, project_id)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not synced yet",
        )

    return _catalog_response(project_id, rows)


@router.patch(
    "/projects/{project_id}/schema/{table_name}",
    response_model=CatalogTableSchema,
)
async def patch_table_annotations(
    project_id: UUID,
    table_name: str,
    payload: TableAnnotationUpdate,
    pool: Pool = Depends(get_pool),
) -> CatalogTableSchema:
    project = await app_db.get_project(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    row = await schema_catalog.update_table_annotations(
        pool, project_id, table_name, payload.model_dump(exclude_unset=True)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    return CatalogTableSchema(**row)


@router.patch(
    "/projects/{project_id}/schema/{table_name}/columns/{column_name}",
    response_model=CatalogTableSchema,
)
async def patch_column_annotations(
    project_id: UUID,
    table_name: str,
    column_name: str,
    payload: ColumnAnnotationUpdate,
    pool: Pool = Depends(get_pool),
) -> CatalogTableSchema:
    project = await app_db.get_project(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    row = await schema_catalog.update_column_annotations(
        pool,
        project_id,
        table_name,
        column_name,
        payload.model_dump(exclude_unset=True),
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table or column not found",
        )

    return CatalogTableSchema(**row)
