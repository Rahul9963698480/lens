from uuid import UUID

import json

from asyncpg import Pool, Record
from fastapi import APIRouter, Depends, HTTPException, status

from app.db import app_db, conversations as conv_db
from app.db.app_db import get_pool
from app.schemas.conversation import (
    ConversationDetail,
    ConversationMessage,
    ConversationSummary,
)

router = APIRouter(tags=["playground"])


def _summary(row: Record) -> ConversationSummary:
    return ConversationSummary.model_validate(dict(row))


def _message(row: Record) -> ConversationMessage:
    data = dict(row)
    used = data.get("queries_used")
    if isinstance(used, str):
        data["queries_used"] = json.loads(used)
    return ConversationMessage.model_validate(data)


async def _require_project(pool: Pool, project_id: UUID) -> None:
    project = await app_db.get_project(pool, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


@router.get(
    "/projects/{project_id}/conversations",
    response_model=list[ConversationSummary],
)
async def list_project_conversations(
    project_id: UUID,
    pool: Pool = Depends(get_pool),
) -> list[ConversationSummary]:
    await _require_project(pool, project_id)
    rows = await conv_db.list_conversations(pool, project_id)
    return [_summary(row) for row in rows]


@router.get(
    "/projects/{project_id}/conversations/{conversation_id}",
    response_model=ConversationDetail,
)
async def get_project_conversation(
    project_id: UUID,
    conversation_id: UUID,
    pool: Pool = Depends(get_pool),
) -> ConversationDetail:
    await _require_project(pool, project_id)
    row = await conv_db.get_conversation(pool, project_id, conversation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    messages = await conv_db.list_messages(pool, conversation_id)
    return ConversationDetail(
        **dict(row),
        messages=[_message(item) for item in messages],
    )


@router.delete(
    "/projects/{project_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_conversation(
    project_id: UUID,
    conversation_id: UUID,
    pool: Pool = Depends(get_pool),
) -> None:
    await _require_project(pool, project_id)
    deleted = await conv_db.delete_conversation(pool, project_id, conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
