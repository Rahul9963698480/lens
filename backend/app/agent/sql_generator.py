"""Agno agent that turns natural language into SQL using table_schema_catalog."""

from __future__ import annotations

import re
from uuid import UUID

import asyncpg
from agno.agent import Agent
from agno.models.openai import OpenAIChat

from app.agent.introspect_schema import create_introspect_schema_tool
from app.config import settings
from app.db import app_db
from app.db.learnings import get_relevant_learnings

SQL_FENCE_RE = re.compile(r"```sql\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
GENERIC_FENCE_RE = re.compile(r"```(?:\w+)?\s*\n(.*?)```", re.DOTALL)

DUCKDB_DIALECT_INSTRUCTIONS = [
    "This spreadsheet project executes SQL on DuckDB (PostgreSQL-compatible dialect).",
    "Use DuckDB-compatible read-only SQL: ILIKE, DATE_TRUNC, CAST(x AS VARCHAR), "
    "standard JOINs, GROUP BY, window functions, and LIMIT.",
    "Do not use SQLite-only functions (strftime, PRAGMA) or Postgres-only extensions "
    "that DuckDB does not support.",
]

AGENT_INSTRUCTIONS = [
    "You are an expert SQL Query Generator agent.",
    "Step 1 — From the user's question, identify ALL tables required to answer it.",
    "Start by mapping question entities to candidate table names "
    "(e.g. 'customers' -> customer, 'stores' -> store).",
    "Step 2 — Introspect ONLY the required tables.",
    "Call `introspect_schema(table_name='<table_name>', include_relationships=true)` "
    "for each initially identified table.",
    "After introspecting an initial table, inspect its relationships to discover "
    "any additional required tables, including bridge or junction tables such as "
    "`film_actor`, and introspect those tables before generating SQL.",
    "If the question identifies a table but the required JOIN or bridge table is "
    "not yet known, first introspect the identified table and inspect its "
    "relationships. Use those relationships to discover additional required "
    "tables before calling `introspect_schema(table_name='all')`.",
    "Call `introspect_schema(table_name='all')` ONLY as a last resort when the "
    "required tables cannot be determined from the user's question or from "
    "relationships discovered through introspection.",
    "NEVER call `introspect_schema(table_name='all')` when the required tables "
    "can be determined from the question or discovered through table relationships.",
    "Do NOT introspect the same table twice in one request.",
    "Do NOT introspect unrelated tables.",
    "Do not generate SQL until schema metadata for all required tables has "
    "been introspected.",
    "Use introspected primary keys, foreign keys, and the relationships "
    "array to determine valid JOIN conditions.",
    "You may ONLY join two tables using a relationship explicitly present "
    "in the schema context you were given (from introspect_schema). You "
    "must NEVER join on a column pair just because the names or types look "
    "similar, and you must NEVER invent a join to force an answer to a "
    "question. If the question requires connecting tables with no declared "
    "or inferred relationship between them, do not guess — respond that no "
    "relationship exists in the schema for this comparison, and answer only "
    "what's possible from a single table if the question allows it.",
    "NEVER write JOIN (or a comma FROM list) unless introspect_schema "
    "returned a relationship whose from_table and to_table match those "
    "tables. If a table's relationships array is empty, that table is "
    "independent — do not join it to any other table.",
    "Never rely on prior knowledge of the database schema.",
    "If a required table or column cannot be confirmed, introspect the relevant "
    "table or return a short error message — do not invent schema.",
    "Based strictly on introspected schema metadata, generate accurate and "
    "optimized SQL matching the user's request.",
    "OUTPUT RULE: If you can produce a valid query from introspected schema, "
    "your final message must contain ONLY a single ```sql code block "
    "with no text before or after it.",
    "If you cannot join because no relationship is declared, do not emit a SQL "
    "block. Reply with a short explanation only — no SQL and no JOIN.",
    "When returning SQL, do not write any text before or after the code block. "
    "No introductions, reasoning, summaries, or commentary in the SQL response.",
]


def extract_sql(content: str) -> str:
    """Pull SQL from a fenced code block. Unfenced text is not treated as SQL."""
    text = (content or "").strip()
    if not text:
        return ""

    match = SQL_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()

    match = GENERIC_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()

    if text.startswith("```") and text.endswith("```"):
        inner = text[3:-3].strip()
        if inner.lower().startswith("sql"):
            inner = inner[3:].lstrip()
        return inner.strip()

    return ""


def _build_agent(
    project_id: UUID,
    pool: asyncpg.Pool,
    *,
    sql_dialect: str = "postgres",
) -> Agent:
    instructions = list(AGENT_INSTRUCTIONS)
    if sql_dialect == "duckdb":
        instructions = instructions + DUCKDB_DIALECT_INSTRUCTIONS
    introspect_schema = create_introspect_schema_tool(
        project_id=project_id,
        pool=pool,
    )
    return Agent(
        name="SQL Generator Agent",
        model=OpenAIChat(id=settings.MODEL_ID, api_key=settings.OPENAI_API_KEY),
        tools=[introspect_schema],
        instructions=instructions,
        expected_output=(
            "Either a single ```sql code block containing only the SQL query, "
            "or a short explanation with no SQL when tables are not linked."
        ),
        markdown=True,
    )


def _format_learnings_context(learnings: list[asyncpg.Record]) -> str:
    lines: list[str] = []
    for row in learnings:
        question = row["question"]
        confirmed_sql = row["confirmed_sql"]
        rule_text = row["rule_text"]
        if confirmed_sql:
            lines.append(f"Similar past question: '{question}' -> SQL: {confirmed_sql}")
        if rule_text:
            lines.append(f"Also remember: {rule_text}")
    return "\n".join(lines)


async def generate_sql_for_project(
    project_id: UUID,
    question: str,
    pool: asyncpg.Pool,
) -> str:
    """Run the schema agent for a project and return generated SQL."""
    project = await app_db.get_project(pool, project_id)
    engine = (project["engine"] or "").strip().lower() if project else ""
    sql_dialect = "duckdb" if engine == "xlsx" else "postgres"

    learnings = await get_relevant_learnings(pool, project_id, question)
    context = _format_learnings_context(learnings)
    prompt = f"{context}\n\nUser question: {question}" if context else question

    agent = _build_agent(project_id, pool, sql_dialect=sql_dialect)
    response = await agent.arun(prompt)
    content = str(response.content or "").strip()
    sql = extract_sql(content)
    if not sql:
        raise ValueError(content or "Agent did not return SQL.")
    return sql
