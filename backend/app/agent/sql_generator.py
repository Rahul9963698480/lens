"""Agno agent that turns natural language into SQL using table_schema_catalog."""

from __future__ import annotations

import re
from uuid import UUID

import asyncpg
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.utils.log import logger

from app.agent.introspect_schema import create_introspect_schema_tool
from app.config import settings
from app.db.learnings import get_relevant_learnings

SQL_FENCE_RE = re.compile(r"```sql\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
GENERIC_FENCE_RE = re.compile(r"```(?:\w+)?\s*\n(.*?)```", re.DOTALL)

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
    "Use introspected primary keys, foreign keys, columns, and relationships "
    "to determine valid JOIN conditions.",
    "Never rely on prior knowledge of the database schema.",
    "If a required table or column cannot be confirmed, introspect the relevant "
    "table or return a short error message — do not invent schema.",
    "Based strictly on introspected schema metadata, generate accurate and "
    "optimized SQL matching the user's request.",
    "OUTPUT RULE (strict): Your final message must contain ONLY a single "
    "```sql code block.",
    "Do NOT write any text before the code block. "
    "Do NOT write any text after the code block.",
    "No introductions, reasoning, summaries, or commentary in the final response.",
]


def extract_sql(content: str) -> str:
    """Pull SQL from a fenced code block, or return trimmed raw content."""
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

    return text


def _build_agent(project_id: UUID, pool: asyncpg.Pool) -> Agent:
    introspect_schema = create_introspect_schema_tool(
        project_id=project_id,
        pool=pool,
    )
    return Agent(
        name="SQL Generator Agent",
        model=OpenAIChat(id=settings.MODEL_ID, api_key=settings.OPENAI_API_KEY),
        tools=[introspect_schema],
        instructions=AGENT_INSTRUCTIONS,
        expected_output="A single ```sql code block containing only the SQL query. No other text.",
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
    learnings = await get_relevant_learnings(pool, project_id, question)
    context = _format_learnings_context(learnings)
    prompt = f"{context}\n\nUser question: {question}" if context else question
    # Temporary: verify retrieval is prepended before the agent runs (STEP 8).
    logger.info(f"Assembled agent prompt:\n{prompt}")

    agent = _build_agent(project_id, pool)
    response = await agent.arun(prompt)
    sql = extract_sql(str(response.content or ""))
    if not sql:
        raise ValueError("Agent did not return SQL.")
    return sql
