from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


ANALYSIS_CONFIRM_MESSAGE = (
    "Running this analysis requires executing queries against your data. Proceed?"
)


class AnalysisStartRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_id: UUID | None = None


class AnalysisStartResponse(BaseModel):
    analysis_id: UUID
    attempt_id: UUID
    conversation_id: UUID
    proposed_sql: str
    message: str


class AnalysisQueryUsed(BaseModel):
    attempt_id: UUID
    sql: str
    result_summary: dict[str, Any]


class AnalysisRunResponse(BaseModel):
    analysis_id: UUID
    answer: str
    queries_used: list[AnalysisQueryUsed]
