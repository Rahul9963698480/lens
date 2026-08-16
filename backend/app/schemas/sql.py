from typing import Any

from pydantic import BaseModel, Field, model_validator


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
    sql: str


class SqlExecuteRequest(BaseModel):
    sql: str = Field(..., min_length=1)


class SqlExecuteResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
