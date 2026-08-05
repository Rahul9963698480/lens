from uuid import UUID

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.db import app_db
from app.db.app_db import get_pool
from app.db.connectors import get_connector, resolve_db_port
from app.schemas.project import (
    ProjectCreate,
    ProjectPreviewResponse,
    ProjectResponse,
    ProjectSchemaResponse,
)

router = APIRouter(tags=["projects"])


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
    return ProjectResponse(**app_db.record_to_dict(row))


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
    deleted = await app_db.delete_project(pool, project_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


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
        connector = get_connector(
            project["engine"],
            project["db_host"],
            project["db_port"],
            project["db_name"],
            project["db_username"],
            project["db_password"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None

    try:
        table_names = await connector.list_tables()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to the project's external database.",
        ) from None

    tables = []
    for table_name in table_names:
        result = await connector.preview_table(table_name, limit=5)
        entry = {"table_name": table_name, "columns": result.get("columns", [])}
        if "error" in result:
            entry["error"] = result["error"]
        else:
            entry["rows"] = result.get("rows", [])
        tables.append(entry)

    return ProjectPreviewResponse(project_id=project_id, tables=tables)


@router.get(
    "/projects/{project_id}/schema",
    response_model=ProjectSchemaResponse,
    response_model_exclude_none=True,
)
async def get_project_schema(
    project_id: UUID,
    pool: Pool = Depends(get_pool),
) -> ProjectSchemaResponse:
    project = await app_db.get_project_with_password(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        connector = get_connector(
            project["engine"],
            project["db_host"],
            project["db_port"],
            project["db_name"],
            project["db_username"],
            project["db_password"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None

    try:
        schema = await connector.get_schema()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to the project's external database.",
        ) from None

    return ProjectSchemaResponse(
        project_id=project_id,
        engine=project["engine"],
        tables=schema.get("tables", []),
        relationships=schema.get("relationships", []),
        note=schema.get("note"),
    )
