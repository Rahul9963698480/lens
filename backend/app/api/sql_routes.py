from uuid import UUID

from asyncpg import Pool, Record
from fastapi import APIRouter, Depends, HTTPException, status

from app.agent import execute_sql_for_project, generate_sql_for_project
from app.config import settings
from app.db import app_db, learnings
from app.db.app_db import get_pool
from app.schemas.sql import (
    AttemptConfirmRequest,
    AttemptFeedbackRequest,
    ConfirmedLearningResponse,
    QueryAttemptResponse,
    SqlExecuteRequest,
    SqlExecuteResponse,
    SqlGenerateRequest,
    SqlGenerateResponse,
)

router = APIRouter(tags=["agent"])


def _attempt_response(row: Record) -> QueryAttemptResponse:
    return QueryAttemptResponse.model_validate(dict(row))


def _learning_response(row: Record) -> ConfirmedLearningResponse:
    return ConfirmedLearningResponse.model_validate(dict(row))


async def _require_project(pool: Pool, project_id: UUID) -> None:
    project = await app_db.get_project(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


async def _require_attempt(pool: Pool, project_id: UUID, attempt_id: UUID) -> Record:
    attempt = await learnings.get_query_attempt(pool, project_id, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return attempt


async def _record_execution(
    pool: Pool,
    project_id: UUID,
    attempt_id: UUID | None,
    *,
    executed_sql: str,
    execution_status: str,
    result_row_count: int | None,
) -> None:
    if attempt_id is None:
        return
    await learnings.update_attempt_execution(
        pool,
        project_id,
        attempt_id,
        executed_sql=executed_sql,
        execution_status=execution_status,
        result_row_count=result_row_count,
    )


# The helper function handles core business logic, project validation, API key checks, and exception translation into HTTP status codes (404, 503, 502).
async def _run_sql_agent(project_id: UUID, question: str, pool: Pool) -> SqlGenerateResponse:
    await _require_project(pool, project_id)

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

    attempt = await learnings.insert_query_attempt(
        pool,
        project_id=project_id,
        question=question,
        generated_sql=sql,
    )
    return SqlGenerateResponse(attempt_id=attempt["id"], sql=sql)


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
    await _require_project(pool, project_id)
    if payload.attempt_id is not None:
        await _require_attempt(pool, project_id, payload.attempt_id)

    try:
        result = await execute_sql_for_project(project_id, payload.sql, pool)
    except ValueError as exc:
        await _record_execution(
            pool,
            project_id,
            payload.attempt_id,
            executed_sql=payload.sql,
            execution_status="error",
            result_row_count=None,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        await _record_execution(
            pool,
            project_id,
            payload.attempt_id,
            executed_sql=payload.sql,
            execution_status="error",
            result_row_count=None,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="SQL execution failed",
        ) from exc

    row_count = int(result.get("row_count", 0))
    await _record_execution(
        pool,
        project_id,
        payload.attempt_id,
        executed_sql=payload.sql,
        execution_status="success",
        result_row_count=row_count,
    )
    return SqlExecuteResponse(
        columns=result.get("columns", []),
        rows=result.get("rows", []),
        row_count=row_count,
    )


@router.patch(
    "/projects/{project_id}/attempts/{attempt_id}/feedback",
    response_model=QueryAttemptResponse,
)
async def set_attempt_feedback(
    project_id: UUID,
    attempt_id: UUID,
    payload: AttemptFeedbackRequest,
    pool: Pool = Depends(get_pool),
) -> QueryAttemptResponse:
    await _require_project(pool, project_id)
    row = await learnings.update_attempt_feedback(
        pool, project_id, attempt_id, payload.feedback
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return _attempt_response(row)


@router.post(
    "/projects/{project_id}/attempts/{attempt_id}/confirm",
    response_model=ConfirmedLearningResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_attempt(
    project_id: UUID,
    attempt_id: UUID,
    payload: AttemptConfirmRequest,
    pool: Pool = Depends(get_pool),
) -> ConfirmedLearningResponse:
    await _require_project(pool, project_id)
    attempt = await _require_attempt(pool, project_id, attempt_id)
    row = await learnings.insert_confirmed_learning(
        pool,
        project_id=project_id,
        question=attempt["question"],
        confirmed_sql=payload.confirmed_sql,
        rule_text=payload.rule_text,
        source_attempt_id=attempt_id,
    )
    return _learning_response(row)
