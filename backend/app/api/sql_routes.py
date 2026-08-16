from uuid import UUID

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, status

from app.agent import execute_sql_for_project, generate_sql_for_project
from app.config import settings
from app.db import app_db
from app.db.app_db import get_pool
from app.schemas.sql import (
    SqlExecuteRequest,
    SqlExecuteResponse,
    SqlGenerateRequest,
    SqlGenerateResponse,
)

router = APIRouter(tags=["agent"])

#The helper function  handles core business logic, project validation, API key checks, and exception translation into HTTP status codes (404, 503, 502).
async def _run_sql_agent(project_id: UUID, question: str, pool: Pool) -> SqlGenerateResponse:
    project = await app_db.get_project(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured",
        )

    try:
        sql = await generate_sql_for_project(project_id, question, pool)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="SQL generation failed",
        ) from exc

    return SqlGenerateResponse(sql=sql)


@router.post(
    "/projects/{project_id}/sql/generate",
    response_model=SqlGenerateResponse,
)
async def generate_sql(
    project_id: UUID,
    payload: SqlGenerateRequest,
    pool: Pool = Depends(get_pool),
) -> SqlGenerateResponse:
    return await _run_sql_agent(project_id, payload.question, pool)


@router.post(
    "/projects/{project_id}/sql/execute",
    response_model=SqlExecuteResponse,
)
async def execute_sql(
    project_id: UUID,
    payload: SqlExecuteRequest,
    pool: Pool = Depends(get_pool),
) -> SqlExecuteResponse:
    project = await app_db.get_project(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        result = await execute_sql_for_project(project_id, payload.sql, pool)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="SQL execution failed",
        ) from exc

    return SqlExecuteResponse(
        columns=result.get("columns", []),
        rows=result.get("rows", []),
        row_count=int(result.get("row_count", 0)),
    )
