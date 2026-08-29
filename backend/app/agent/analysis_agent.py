"""Agno analysis agent — proposes SQL or synthesizes answers as text.

Never given an execute_query tool. Backend code runs SQL via
execute_sql_for_project; prior results are injected as plain prompt text.

One /analysis/{id}/run keeps a single Agent instance (InMemoryDb +
add_history_to_context) so introspect_schema results from the first LLM
turn are reused on later turns. /analysis/start is a separate HTTP
request and still builds a fresh agent.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
from agno.agent import Agent
from agno.db.in_memory import InMemoryDb
from agno.models.openai import OpenAIChat

from app.agent.introspect_schema import (
    create_introspect_schema_tool,
    schema_context_for_sql,
)
from app.agent.sql_executor import execute_sql_for_project
from app.agent.sql_generator import _format_learnings_context, extract_sql
from app.config import settings
from app.db import learnings
from app.db.learnings import get_relevant_learnings

logger = logging.getLogger(__name__)

MAX_ANALYSIS_QUERIES = 2
RESULT_PREVIEW_ROWS = 50
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
AnalysisProgress = Callable[[str, str], Awaitable[None]]

ANALYSIS_INSTRUCTIONS = [
    "You are an expert data analysis agent.",
    "You NEVER execute SQL. You have no execute_query tool and must never "
    "claim to have run a query. The backend executes SQL separately.",
    "Your only tool is introspect_schema — use it to look up table metadata "
    "before proposing SQL. You must not call any other tool.",
    "Step 1 — From the user's question, identify ALL tables required to answer it.",
    "Start by mapping question entities to candidate table names "
    "(e.g. 'customers' -> customer, 'stores' -> store).",
    "Step 2 — Introspect ONLY the required tables in ONE tool call.",
    "Call `introspect_schema(table_name='table1,table2', include_relationships=true)` "
    "with every initially identified table in a comma-separated list. "
    "Do not make a separate introspect_schema call per table.",
    "After introspecting, inspect relationships to discover "
    "any additional required tables, including bridge or junction tables such as "
    "`film_actor`, and introspect those missing tables in one more batched call "
    "before generating SQL.",
    "If the question identifies a table but the required JOIN or bridge table is "
    "not yet known, first introspect the identified table and inspect its "
    "relationships. Use those relationships to discover additional required "
    "tables before calling `introspect_schema(table_name='all')`.",
    "Call `introspect_schema(table_name='all')` ONLY as a last resort when the "
    "required tables cannot be determined from the user's question or from "
    "relationships discovered through introspection.",
    "NEVER call `introspect_schema(table_name='all')` when the required tables "
    "can be determined from the question or discovered through table relationships.",
    "Do NOT introspect the same table twice in one request or later in the "
    "same conversation.",
    "Schema returned by earlier introspect_schema calls in this conversation "
    "is still valid — reuse it. Do not call introspect_schema again for a "
    "table you already inspected.",
    "Do NOT introspect unrelated tables.",
    "Do not generate SQL until schema metadata for all required tables has "
    "been introspected or is already present in this conversation.",
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
    "table or return a short synthesize answer — do not invent schema.",
    "Prefer one well-targeted query. Only propose a second query when the "
    "first result is insufficient to answer the original question.",
    "OUTPUT RULE: Your final message must be a single JSON object with no "
    "text before or after it.",
    'To propose SQL: {"action": "run_query", "sql": "SELECT ..."}',
    'To give a final answer: {"action": "synthesize", "answer": "..."}',
    "When proposing SQL, put the full query in the sql field — no markdown fences.",
    "When synthesizing, write a readable analysis answer — not one long paragraph "
    "and never a markdown table (no | pipes). Tables belong in the Data tab.",
    "Start with one short takeaway sentence, then a blank line, then bullet points "
    "(- item) for each group or fact. Keep each bullet to one line.",
    "Example: 'Hyderabad has the most employees.\\n\\n- Hyderabad: 10\\n- Bengaluru: 8'",
    "Omit groups with zero/null values unless the question asks for them. "
    "Escape newlines in JSON as \\n. Do not wrap the JSON object in markdown fences.",
]


class AnalysisNotFoundError(LookupError):
    """No query_attempts rows exist for this analysis_id on the project."""


class AnalysisAlreadyRunError(RuntimeError):
    """This analysis has already executed; refuse a second /run."""


def _build_analysis_agent(
    project_id: UUID,
    pool: asyncpg.Pool,
    *,
    session_id: str | None = None,
) -> Agent:
    introspect_schema = create_introspect_schema_tool(
        project_id=project_id,
        pool=pool,
    )
    # InMemoryDb is required: add_history_to_context is a no-op without a db.
    return Agent(
        name="Analysis Agent",
        model=OpenAIChat(id=settings.MODEL_ID, api_key=settings.OPENAI_API_KEY),
        tools=[introspect_schema],
        instructions=ANALYSIS_INSTRUCTIONS,
        expected_output=(
            'A single JSON object: {"action": "run_query", "sql": "..."} '
            'or {"action": "synthesize", "answer": "..."}.'
        ),
        markdown=False,
        db=InMemoryDb(),
        add_history_to_context=True,
        store_tool_messages=True,
        session_id=session_id,
    )


def _truncate_rows(result: dict[str, Any], limit: int = RESULT_PREVIEW_ROWS) -> list[Any]:
    rows = result.get("rows") or []
    if not isinstance(rows, list):
        return []
    return rows[:limit]


def summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    """Compact result for API responses and agent prompt context."""
    if result.get("status") == "error":
        return {
            "status": "error",
            "message": result.get("message") or "SQL execution failed",
        }
    rows_preview = _truncate_rows(result)
    return {
        "status": result.get("status") or "ok",
        "columns": result.get("columns") or [],
        "row_count": int(result.get("row_count") or len(result.get("rows") or [])),
        "rows_preview": rows_preview,
    }


def _format_prior_results(prior_results: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, raw in enumerate(prior_results, start=1):
        summary = summarize_result(raw)
        if summary.get("status") == "error":
            blocks.append(
                f"Query {index} failed:\n{summary.get('message', 'SQL execution failed')}"
            )
            continue
        rows_json = json.dumps(summary["rows_preview"], default=str)
        blocks.append(
            f"Query {index} result:\n"
            f"columns: {summary['columns']}\n"
            f"row_count: {summary['row_count']}\n"
            f"rows (first {RESULT_PREVIEW_ROWS}): {rows_json}"
        )
    return "\n\n".join(blocks)


def build_analysis_prompt(
    question: str,
    *,
    prior_results: list[dict[str, Any]] | None = None,
    force_synthesize: bool = False,
    learnings_context: str = "",
    schema_in_session: bool = False,
    schema_context: str = "",
) -> str:
    """Build the user prompt. Prior results are plain text, never a tool result."""
    parts: list[str] = []
    if learnings_context:
        parts.append(learnings_context)
    if schema_context:
        parts.append(
            "Schema for tables in the confirmed SQL "
            "(reuse this; do not introspect these tables again):"
        )
        parts.append(schema_context)
        schema_in_session = True
    parts.append(f"Original question: {question}")

    if prior_results:
        parts.append("Here is the result of your previous query:")
        parts.append(_format_prior_results(prior_results))

    if force_synthesize:
        parts.append(
            "Write your final answer now using only what you have — "
            "no more queries are available."
        )
        parts.append(
            'Return {"action": "synthesize", "answer": "..."} — do not propose SQL. '
            "Do not call introspect_schema. Put a one-sentence takeaway, a blank line, "
            "then bullet points (- item). Never use a markdown table."
        )
    elif prior_results:
        if schema_in_session:
            parts.append(
                "Schema from earlier introspect_schema calls in this conversation "
                "is still valid. Do not call introspect_schema again unless you "
                "need a table that has not been introspected yet."
            )
        parts.append(
            "Do you need another query, or can you answer the original question now?"
        )
        parts.append(
            'If you need another query, return {"action": "run_query", "sql": "..."}. '
            'If you can answer now, return {"action": "synthesize", "answer": "..."}.'
        )
    else:
        parts.append(
            "Propose the first SQL query needed to start answering this question. "
            'Return {"action": "run_query", "sql": "SELECT ..."}.'
        )

    return "\n\n".join(parts)


def _log_agent_tool_calls(response: Any, *, turn: str) -> None:
    """Temporary: log every tool the model invoked on this turn."""
    stamp = datetime.now(timezone.utc).isoformat()
    tools = getattr(response, "tools", None) or []
    if not tools:
        logger.info(
            "analysis_agent tools_used turn=%s count=0 timestamp=%s",
            turn,
            stamp,
        )
        return
    for tool in tools:
        logger.info(
            "analysis_agent tools_used turn=%s tool=%s args=%s timestamp=%s",
            turn,
            getattr(tool, "tool_name", None),
            getattr(tool, "tool_args", None),
            stamp,
        )


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = (text or "").strip()
    if not stripped:
        return None

    fence = JSON_FENCE_RE.search(stripped)
    if fence:
        stripped = fence.group(1).strip()

    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(stripped[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def parse_analysis_response(
    content: str,
    *,
    allow_sql_fallback: bool = True,
) -> dict[str, Any]:
    """Parse agent text into {action, sql} or {action, answer}."""
    parsed = _extract_json_object(content)
    if parsed is not None:
        action = parsed.get("action")
        if action == "run_query":
            sql = (parsed.get("sql") or "").strip()
            if not sql and allow_sql_fallback:
                sql = extract_sql(content)
            if sql:
                return {"action": "run_query", "sql": sql}
        if action == "synthesize":
            answer = str(parsed.get("answer") or "").strip()
            if answer:
                return {"action": "synthesize", "answer": answer}
        if parsed.get("sql") and allow_sql_fallback:
            return {"action": "run_query", "sql": str(parsed["sql"]).strip()}
        if parsed.get("answer"):
            return {"action": "synthesize", "answer": str(parsed["answer"]).strip()}

    if allow_sql_fallback:
        sql = extract_sql(content)
        if sql:
            return {"action": "run_query", "sql": sql}

    raise ValueError(content or "Analysis agent did not return a valid action.")


def _coerce_synthesize(content: str, parsed: dict[str, Any] | None) -> dict[str, Any]:
    if parsed and parsed.get("action") == "synthesize" and parsed.get("answer"):
        return parsed
    answer = ""
    if parsed:
        answer = str(parsed.get("answer") or parsed.get("sql") or "").strip()
    if not answer:
        answer = (content or "").strip()
    if not answer:
        answer = "Unable to synthesize an answer from the available results."
    return {"action": "synthesize", "answer": answer}


async def generate_analysis_query(
    *,
    project_id: UUID,
    pool: asyncpg.Pool,
    question: str,
    prior_results: list[dict[str, Any]] | None = None,
    force_synthesize: bool = False,
    agent: Agent | None = None,
    schema_in_session: bool = False,
    learnings_context: str | None = None,
    schema_context: str = "",
) -> dict[str, Any]:
    """Ask the analysis agent to propose SQL or synthesize an answer.

    prior_results, if present, is passed as plain text in the prompt — not as
    a tool result. The agent has no execute_query tool.

    Pass a reusable ``agent`` (from run_analysis_chain) so later turns in the
    same /run keep introspect_schema results in session history. /analysis/start
    omits it and builds a fresh agent.

    Pass ``learnings_context`` to skip a repeated confirmed-learnings lookup.
    """
    if learnings_context is None:
        learnings_rows = await get_relevant_learnings(pool, project_id, question)
        learnings_context = _format_learnings_context(learnings_rows)
    prompt = build_analysis_prompt(
        question,
        prior_results=prior_results,
        force_synthesize=force_synthesize,
        learnings_context=learnings_context,
        schema_in_session=schema_in_session,
        schema_context=schema_context,
    )

    reuse_session = agent is not None
    if agent is None:
        agent = _build_analysis_agent(project_id, pool)
    turn = "synthesize" if force_synthesize else ("followup" if prior_results else "start")
    logger.info(
        "analysis_agent arun force_synthesize=%s reuse_session=%s "
        "schema_in_session=%s tool_count=%s",
        force_synthesize,
        reuse_session,
        schema_in_session,
        len(agent.tools or []),
    )
    response = await agent.arun(prompt)
    _log_agent_tool_calls(response, turn=turn)
    content = str(response.content or "").strip()

    if force_synthesize:
        try:
            parsed = parse_analysis_response(content, allow_sql_fallback=False)
        except ValueError:
            parsed = None
        return _coerce_synthesize(content, parsed)

    return parse_analysis_response(content, allow_sql_fallback=True)


def _attempt_already_executed(status: str | None) -> bool:
    return status not in (None, "not_run")


def _result_needs_followup(result: dict[str, Any]) -> bool:
    """Second query only when the first result cannot answer the question."""
    if result.get("status") == "error":
        return True
    return int(result.get("row_count") or 0) <= 0


async def _emit_progress(
    on_progress: AnalysisProgress | None,
    stage: str,
    message: str = "",
) -> None:
    if on_progress is None:
        return
    await on_progress(stage, message)


def _chain_payload(
    analysis_id: UUID,
    answer: str,
    queries_run: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "analysis_id": analysis_id,
        "answer": answer,
        "queries_used": [
            {
                "attempt_id": item["attempt_id"],
                "sql": item["sql"],
                "result_summary": summarize_result(item["result"]),
            }
            for item in queries_run
        ],
    }


async def run_analysis_chain(
    *,
    project_id: UUID,
    analysis_id: UUID,
    pool: asyncpg.Pool,
    on_progress: AnalysisProgress | None = None,
) -> dict[str, Any]:
    """Execute the confirmed analysis: at most MAX_ANALYSIS_QUERIES queries.

    Happy path is execute then one synthesize LLM call. A follow-up LLM runs
    only when the first result is empty or failed. A second synthesize is
    skipped when that follow-up already returned an answer.

    Schema for tables in the confirmed SQL is injected from the catalog so
    /run does not re-introspect. Learnings are loaded once per chain.
    """
    attempts = await learnings.list_attempts_for_analysis(pool, project_id, analysis_id)
    if not attempts:
        raise AnalysisNotFoundError("Analysis not found")
    if any(_attempt_already_executed(row["execution_status"]) for row in attempts):
        raise AnalysisAlreadyRunError("Analysis has already been run")

    first = attempts[0]
    question = first["question"]
    current_sql = first["generated_sql"]
    current_attempt_id = first["id"]
    queries_run: list[dict[str, Any]] = []
    pending_answer: str | None = None

    learnings_rows = await get_relevant_learnings(pool, project_id, question)
    learnings_context = _format_learnings_context(learnings_rows)
    schema_context = await schema_context_for_sql(pool, project_id, current_sql)

    agent = _build_analysis_agent(
        project_id, pool, session_id=str(analysis_id)
    )

    for _ in range(MAX_ANALYSIS_QUERIES):
        await _emit_progress(
            on_progress,
            "executing",
            f"Running query {len(queries_run) + 1}…",
        )
        result = await _execute_and_record(
            pool=pool,
            project_id=project_id,
            attempt_id=current_attempt_id,
            sql=current_sql,
        )
        queries_run.append(
            {
                "attempt_id": current_attempt_id,
                "sql": current_sql,
                "result": result,
            }
        )
        logger.info(
            "analysis_id=%s executed attempt_id=%s queries_run=%s",
            analysis_id,
            current_attempt_id,
            len(queries_run),
        )

        if len(queries_run) >= MAX_ANALYSIS_QUERIES:
            break
        if not _result_needs_followup(result):
            break

        await _emit_progress(
            on_progress,
            "followup",
            "Checking if another query is needed…",
        )
        decision = await generate_analysis_query(
            project_id=project_id,
            pool=pool,
            question=question,
            prior_results=[item["result"] for item in queries_run],
            agent=agent,
            schema_in_session=True,
            learnings_context=learnings_context,
            schema_context=schema_context,
        )
        if decision.get("action") == "synthesize" and decision.get("answer"):
            pending_answer = str(decision["answer"])
            break
        if decision.get("action") != "run_query" or not decision.get("sql"):
            break

        new_attempt = await learnings.insert_query_attempt(
            pool,
            project_id=project_id,
            question=question,
            generated_sql=decision["sql"],
            analysis_id=analysis_id,
        )
        current_sql = decision["sql"]
        current_attempt_id = new_attempt["id"]
        extra_schema = await schema_context_for_sql(pool, project_id, current_sql)
        if extra_schema:
            schema_context = extra_schema

    if pending_answer:
        await _emit_progress(on_progress, "complete", "Done")
        return _chain_payload(analysis_id, pending_answer, queries_run)

    await _emit_progress(on_progress, "synthesizing", "Writing answer…")
    synthesized = await generate_analysis_query(
        project_id=project_id,
        pool=pool,
        question=question,
        prior_results=[item["result"] for item in queries_run],
        force_synthesize=True,
        agent=agent,
        schema_in_session=True,
        learnings_context=learnings_context,
        schema_context=schema_context,
    )
    await _emit_progress(on_progress, "complete", "Done")
    return _chain_payload(analysis_id, synthesized["answer"], queries_run)


async def _execute_and_record(
    *,
    pool: asyncpg.Pool,
    project_id: UUID,
    attempt_id: UUID,
    sql: str,
) -> dict[str, Any]:
    """Run one query through the existing execute-sql path and persist status."""
    try:
        payload = await execute_sql_for_project(
            project_id, sql, pool, max_rows=RESULT_PREVIEW_ROWS
        )
    except ValueError as exc:
        await learnings.update_attempt_execution(
            pool,
            project_id,
            attempt_id,
            executed_sql=sql,
            execution_status="error",
            result_row_count=None,
        )
        return {"status": "error", "message": str(exc)}
    except Exception:
        logger.exception("analysis execute failed attempt_id=%s", attempt_id)
        await learnings.update_attempt_execution(
            pool,
            project_id,
            attempt_id,
            executed_sql=sql,
            execution_status="error",
            result_row_count=None,
        )
        return {"status": "error", "message": "SQL execution failed"}

    row_count = int(payload.get("row_count", 0))
    await learnings.update_attempt_execution(
        pool,
        project_id,
        attempt_id,
        executed_sql=sql,
        execution_status="success",
        result_row_count=row_count,
    )
    return payload

