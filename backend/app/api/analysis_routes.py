import asyncio
import json
from uuid import UUID, uuid4

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.agent.analysis_agent import (
    AnalysisAlreadyRunError,
    AnalysisNotFoundError,
    format_conversation_history,
    generate_analysis_query,
    run_analysis_chain,
)
from app.config import settings
from app.db import app_db, conversations as conv_db, learnings
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


def _wants_event_stream(request: Request, stream: bool) -> bool:
    if stream:
        return True
    accept = request.headers.get("accept", "")
    return "text/event-stream" in accept.lower()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


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

    conversation_id = payload.conversation_id
    if conversation_id is not None:
        existing = await conv_db.get_conversation(pool, project_id, conversation_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
    else:
        created = await conv_db.create_conversation(
            pool,
            project_id=project_id,
            title=conv_db.conversation_title(payload.question),
        )
        conversation_id = created["id"]

    prior_turns = await conv_db.list_recent_turns(pool, conversation_id, limit=5)
    conversation_context = format_conversation_history(prior_turns)

    try:
        decision = await generate_analysis_query(
            project_id=project_id,
            pool=pool,
            question=payload.question,
            prior_results=None,
            conversation_context=conversation_context,
            persist_chat=True,
            session_id=str(conversation_id),
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
        conversation_id=conversation_id,
        proposed_sql=sql,
        message=ANALYSIS_CONFIRM_MESSAGE,
    )


@router.post(
    "/projects/{project_id}/analysis/{analysis_id}/run",
)
async def run_analysis(
    project_id: UUID,
    analysis_id: UUID,
    request: Request,
    pool: Pool = Depends(get_pool),
    stream: bool = Query(False),
    conversation_id: UUID | None = Query(None),
):
    await _require_project(pool, project_id)
    _require_openai_key()

    if not _wants_event_stream(request, stream):
        payload = await _run_analysis_payload(project_id, analysis_id, pool)
        await _persist_conversation_turn(
            pool, project_id, conversation_id, analysis_id, payload
        )
        return AnalysisRunResponse.model_validate(payload)

    queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

    async def on_progress(stage: str, message: str = "") -> None:
        await queue.put(("progress", {"stage": stage, "message": message}))

    async def run() -> None:
        try:
            payload = await run_analysis_chain(
                project_id=project_id,
                analysis_id=analysis_id,
                pool=pool,
                on_progress=on_progress,
            )
            await _persist_conversation_turn(
                pool, project_id, conversation_id, analysis_id, payload
            )
            body = AnalysisRunResponse.model_validate(payload).model_dump(mode="json")
            await queue.put(("complete", body))
        except AnalysisNotFoundError:
            await queue.put(("error", {"detail": "Analysis not found", "status": 404}))
        except AnalysisAlreadyRunError:
            await queue.put(("error", {"detail": "Analysis has already been run", "status": 409}))
        except ValueError as exc:
            await queue.put(("error", {"detail": str(exc), "status": 502}))
        except Exception:
            await queue.put(("error", {"detail": "Analysis execution failed", "status": 502}))
        finally:
            await queue.put(None)

    async def event_stream():
        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event, data = item
                yield _sse(event, data)
                if event in ("complete", "error"):
                    break
        finally:
            await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _persist_conversation_turn(
    pool: Pool,
    project_id: UUID,
    conversation_id: UUID | None,
    analysis_id: UUID,
    payload: dict,
) -> None:
    if conversation_id is None:
        return
    existing = await conv_db.get_conversation(pool, project_id, conversation_id)
    if existing is None:
        return
    attempts = await learnings.list_attempts_for_analysis(pool, project_id, analysis_id)
    question = attempts[0]["question"] if attempts else ""
    queries = payload.get("queries_used") or []
    sql = "\n\n".join(str(item.get("sql") or "") for item in queries).strip()
    await conv_db.insert_message(
        pool,
        conversation_id=conversation_id,
        question=question,
        sql=sql,
        answer=str(payload.get("answer") or ""),
        analysis_id=analysis_id,
        queries_used=queries,
    )


async def _run_analysis_payload(
    project_id: UUID,
    analysis_id: UUID,
    pool: Pool,
) -> dict:
    try:
        return await run_analysis_chain(
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
