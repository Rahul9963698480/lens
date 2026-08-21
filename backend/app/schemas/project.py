from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    name: str
    engine: Literal["postgres", "mongodb"]
    db_host: str
    db_name: str
    db_username: str
    db_password: str

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name is required")
        return normalized


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    engine: str
    db_host: str
    db_port: int
    db_name: str
    db_username: str
    status: str
    created_at: datetime


class ErrorResponse(BaseModel):
    error: str


class TablePreview(BaseModel):
    table_name: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] | None = None
    error: str | None = None


class ProjectPreviewResponse(BaseModel):
    project_id: UUID
    tables: list[TablePreview]


class SchemaColumn(BaseModel):
    name: str
    type: str | None = None
    inferred_type: str | None = None
    nullable: bool | None = None
    primary_key: bool | None = None
    foreign_key: str | None = None
    presence_pct: float | None = None
    description: str | None = None
    business_name: str | None = None
    value_mappings: dict[str, Any] | None = None
    null_meanings: str | None = None
    caveats: str | None = None


class SchemaRelationship(BaseModel):
    """Engine-agnostic relationship between two tables/collections."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: Literal["many_to_one", "one_to_one", "one_to_many"] = "many_to_one"
    confidence: Literal["declared", "inferred"]


class CatalogTableSchema(BaseModel):
    table_name: str
    table_description: str | None = None
    business_name: str | None = None
    columns: list[SchemaColumn] = Field(default_factory=list)
    relationships: list[SchemaRelationship] = Field(default_factory=list)
    inferred: bool
    updated_at: datetime


class ProjectSchemaResponse(BaseModel):
    project_id: UUID
    db_name: str
    tables: list[CatalogTableSchema]


class TableAnnotationUpdate(BaseModel):
    table_description: str | None = None
    business_name: str | None = None


class ColumnAnnotationUpdate(BaseModel):
    description: str | None = None
    business_name: str | None = None
    value_mappings: dict[str, Any] | None = None
    null_meanings: str | None = None
    caveats: str | None = None
