from uuid import UUID, uuid4

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, status

from app.agent.analysis_agent import (
    AnalysisAlreadyRunError,
    AnalysisNotFoundError,
    generate_analysis_query,
    run_analysis_chain,
)
from app.config import settings
from app.db import app_db, learnings
from app.db.app_db import get_pool
from app.schemas.analysis import (
    ANALYSIS_CONFIRM_MESSAGE,
    AnalysisRunResponse,
    AnalysisStartRequest,
    AnalysisStartResponse,
)

router = APIRouter(tags=["agent"])


async def _require_project(pool: Pool, project_id: UUID) -> None:
    project = await app_db.get_project(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


def _require_openai_key() -> None:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured",
        )


@router.post(
    "/projects/{project_id}/analysis/start",
    response_model=AnalysisStartResponse,
)
async def start_analysis(
    project_id: UUID,
    payload: AnalysisStartRequest,
    pool: Pool = Depends(get_pool),
) -> AnalysisStartResponse:
    await _require_project(pool, project_id)
    _require_openai_key()

    try:
        decision = await generate_analysis_query(
            project_id=project_id,
            pool=pool,
            question=payload.question,
            prior_results=None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Analysis query generation failed",
        ) from exc

    sql = (decision.get("sql") or "").strip() if decision.get("action") == "run_query" else ""
    if not sql:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Analysis agent did not propose a query",
        )

    analysis_id = uuid4()
    attempt = await learnings.insert_query_attempt(
        pool,
        project_id=project_id,
        question=payload.question,
        generated_sql=sql,
        analysis_id=analysis_id,
    )
    return AnalysisStartResponse(
        analysis_id=analysis_id,
        attempt_id=attempt["id"],
        proposed_sql=sql,
        message=ANALYSIS_CONFIRM_MESSAGE,
    )


@router.post(
    "/projects/{project_id}/analysis/{analysis_id}/run",
    response_model=AnalysisRunResponse,
)
async def run_analysis(
    project_id: UUID,
    analysis_id: UUID,
    pool: Pool = Depends(get_pool),
) -> AnalysisRunResponse:
    await _require_project(pool, project_id)
    _require_openai_key()

    try:
        payload = await run_analysis_chain(
            project_id=project_id,
            analysis_id=analysis_id,
            pool=pool,
        )
    except AnalysisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        ) from exc
    except AnalysisAlreadyRunError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis has already been run",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Analysis execution failed",
        ) from exc

    return AnalysisRunResponse.model_validate(payload)
