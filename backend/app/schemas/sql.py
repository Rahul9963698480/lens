from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SqlGenerateRequest(BaseModel):
    question: str = Field(..., min_length=1)


class ProjectChatRequest(BaseModel):
    """Accepts `question` or legacy `message` from older clients."""

    question: str | None = Field(default=None, min_length=1)
    message: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_question_or_message(self) -> "ProjectChatRequest":
        if self.question:
            return self
        if self.message:
            self.question = self.message
            return self
        raise ValueError("Either 'question' or 'message' is required")


class SqlGenerateResponse(BaseModel):
    attempt_id: UUID
    sql: str


class SqlExecuteRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    attempt_id: UUID | None = None


class SqlExecuteResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class AttemptFeedbackRequest(BaseModel):
    feedback: Literal["correct", "incorrect"]


class QueryAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    question: str
    generated_sql: str
    executed_sql: str | None = None
    execution_status: str | None = None
    result_row_count: int | None = None
    feedback: str
    created_at: datetime


class AttemptConfirmRequest(BaseModel):
    confirmed_sql: str = Field(..., min_length=1)
    rule_text: str | None = None


class ConfirmedLearningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    question: str
    confirmed_sql: str
    rule_text: str | None = None
    source_attempt_id: UUID | None = None
    confirmed_at: datetime
    active: bool
