"""Infer table relationships from overlapping column values in xlsx SQLite files."""

from __future__ import annotations

import inspect
import logging
import re
import sqlite3
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

OVERLAP_THRESHOLD = 0.9
SAMPLE_LIMIT = 1000
MIN_DISTINCT = 2
HIGH_UNIQUENESS_RATIO = 0.8
LOW_UNIQUENESS_RATIO = 0.3
VERIFY_TIMEOUT_SECONDS = 20.0
_PATTERN_MAJORITY = 0.5
_MAX_LITERAL_PREFIX = 4

_SKIP_TYPES = frozenset({"REAL", "FLOAT", "DOUBLE", "NUMERIC"})
_YES_RE = re.compile(r"^\s*(yes)\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

logger = logging.getLogger(__name__)

RelationshipVerifier = Callable[[dict[str, Any]], bool | Awaitable[bool]]


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _column_type(raw: str | None) -> str:
    return (raw or "TEXT").strip().upper() or "TEXT"


def _get_columns(conn: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    rows = conn.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()
    return [(str(r[1]), _column_type(r[2])) for r in rows]


def _get_distinct_values(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    limit: int,
) -> set[Any]:
    sql = (
        f"SELECT DISTINCT {_quote_ident(column)} FROM {_quote_ident(table)} "
        f"WHERE {_quote_ident(column)} IS NOT NULL LIMIT {int(limit)}"
    )
    return {row[0] for row in conn.execute(sql)}


def _table_row_count(conn: sqlite3.Connection, table: str) -> int:
    sql = f"SELECT COUNT(*) FROM {_quote_ident(table)}"
    return int(conn.execute(sql).fetchone()[0])


def _uniqueness_ratio(
    distinct_count: int, row_count: int, sample_limit: int
) -> float:
    if distinct_count >= sample_limit:
        return 1.0
    if row_count <= 0:
        return 0.0
    return distinct_count / row_count


def _unordered_key(
    table_a: str, col_a: str, table_b: str, col_b: str
) -> frozenset[tuple[str, str]]:
    return frozenset(((table_a, col_a), (table_b, col_b)))


def _pick_direction(
    table_a: str,
    col_a: str,
    n_a: int,
    table_b: str,
    col_b: str,
    n_b: int,
) -> tuple[str, str, str, str]:
    """Point the many/high-cardinality side at the few/unique side."""
    if n_a != n_b:
        if n_a > n_b:
            return table_a, col_a, table_b, col_b
        return table_b, col_b, table_a, col_a
    if (table_a, col_a) <= (table_b, col_b):
        return table_a, col_a, table_b, col_b
    return table_b, col_b, table_a, col_a


def _catalog_rel(rel: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in rel.items() if not str(k).startswith("_")}


def _nonempty_texts(values: Sequence[Any]) -> list[tuple[Any, str]]:
    out: list[tuple[Any, str]] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        out.append((value, text))
    return out


def _is_numeric_text(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _is_numeric_value(value: Any, text: str) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    return _is_numeric_text(text)


def _is_integer_like(value: Any, text: str) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return value.is_integer()
    stripped = text.strip().lstrip("+-")
    return stripped.isdigit()


def _duplicate_phrase(uniqueness: float) -> str:
    if uniqueness >= 0.99:
        return "no duplicates"
    if uniqueness >= HIGH_UNIQUENESS_RATIO:
        return "mostly unique"
    return "some duplicates"


def _length_phrase(texts: Sequence[str]) -> str:
    lengths = [len(t) for t in texts]
    lo, hi = min(lengths), max(lengths)
    if lo == hi:
        return f"fixed-length {lo}"
    return f"lengths {lo}-{hi}"


def _digit_width_range(width: int) -> str:
    if width <= 1:
        return "range 0-9"
    lo = 10 ** (width - 1)
    hi = 10**width - 1
    return f"range {lo}-{hi}"


def _leading_non_digit_prefix(text: str) -> str:
    for index, char in enumerate(text):
        if char.isdigit():
            return text[:index]
    return ""


def _shared_format_prefix(texts: Sequence[str]) -> str | None:
    """Return a short shared non-digit prefix when every remainder is digits."""
    prefixes = [_leading_non_digit_prefix(t) for t in texts]
    if not prefixes or not prefixes[0]:
        return None
    prefix = prefixes[0]
    if not (1 <= len(prefix) <= _MAX_LITERAL_PREFIX):
        return None
    if prefix.isdigit():
        return None
    if not any(char.isalpha() or not char.isalnum() for char in prefix):
        return None
    if any(p != prefix for p in prefixes):
        return None
    rests = [t[len(prefix) :] for t in texts]
    if not rests or not all(r.isdigit() and r for r in rests):
        return None
    return prefix


def describe_column_pattern(
    values: Sequence[Any],
    uniqueness: float | None = None,
) -> str:
    """Summarize a column's value shape without copying any cell into the string.

    Computed entirely server-side. The result is safe to send to an LLM provider.
    """
    pairs = _nonempty_texts(values)
    if not pairs:
        return "empty"
    texts = [text for _value, text in pairs]
    n = len(texts)
    if uniqueness is None:
        uniqueness = len(set(texts)) / n
    dup = _duplicate_phrase(uniqueness)

    if sum(1 for t in texts if _EMAIL_RE.match(t)) / n >= _PATTERN_MAJORITY:
        return f"email-like strings, {_length_phrase(texts)}, {dup}"
    if sum(1 for t in texts if _UUID_RE.match(t)) / n >= _PATTERN_MAJORITY:
        return f"UUID-like hex strings, {dup}"

    numeric_n = sum(1 for value, text in pairs if _is_numeric_value(value, text))
    if numeric_n / n >= _PATTERN_MAJORITY:
        int_pairs = [
            (value, text) for value, text in pairs if _is_integer_like(value, text)
        ]
        if len(int_pairs) / n >= _PATTERN_MAJORITY:
            widths: list[int] = []
            for value, text in int_pairs:
                digits = text.strip().lstrip("+-")
                if digits.isdigit():
                    widths.append(max(len(digits), 1))
                else:
                    widths.append(len(str(abs(int(value)))))
            w_min, w_max = min(widths), max(widths)
            if w_min == w_max:
                return f"{w_min}-digit numeric IDs, {dup}, {_digit_width_range(w_min)}"
            return f"{w_min}-{w_max} digit integers, {dup}"
        return f"decimal numbers, {dup}"

    prefix = _shared_format_prefix(texts)
    if prefix is not None:
        rest_lens = [len(t) - len(prefix) for t in texts]
        mask_len = max(rest_lens)
        mask = "#" * mask_len
        return f"alphanumeric strings, format similar to '{prefix}{mask}', {dup}"

    length_bit = _length_phrase(texts)
    letters_only = sum(1 for t in texts if t.replace(" ", "").isalpha())
    if letters_only / n >= _PATTERN_MAJORITY:
        return f"alphabetic strings, {length_bit}, {dup}"
    alnum = sum(
        1 for t in texts if t.replace("-", "").replace("_", "").isalnum()
    )
    if alnum / n >= _PATTERN_MAJORITY:
        return f"alphanumeric strings, {length_bit}, {dup}"
    return f"mixed strings, {length_bit}, {dup}"


def infer_relationship_candidates(
    conn: sqlite3.Connection,
    tables: list[str],
    *,
    overlap_threshold: float = OVERLAP_THRESHOLD,
    sample_limit: int = SAMPLE_LIMIT,
) -> list[dict[str, Any]]:
    """Return overlap candidates that pass the cardinality gate, with extras.

    Extra keys (`_overlap_ratio`, `_unique_side_uniqueness`, `_values_a`,
    `_values_b`, `_uniqueness_a`, `_uniqueness_b`) are for LLM verification
    only and must not be stored in the catalog.
    """
    column_stats: dict[tuple[str, str], tuple[set[Any], float]] = {}
    for table in tables:
        row_count = _table_row_count(conn, table)
        for col, col_type in _get_columns(conn, table):
            if col_type in _SKIP_TYPES:
                continue
            values = _get_distinct_values(conn, table, col, sample_limit)
            distinct_count = len(values)
            if distinct_count < MIN_DISTINCT:
                continue
            uniqueness = _uniqueness_ratio(distinct_count, row_count, sample_limit)
            column_stats[(table, col)] = (values, uniqueness)

    best: dict[frozenset[tuple[str, str]], dict[str, Any]] = {}
    items = list(column_stats.items())
    for (table_a, col_a), (values_a, uniq_a) in items:
        for (table_b, col_b), (values_b, uniq_b) in items:
            if table_a == table_b:
                continue
            overlap = len(values_a & values_b) / min(len(values_a), len(values_b))
            if overlap <= overlap_threshold:
                continue
            if uniq_a < LOW_UNIQUENESS_RATIO and uniq_b < LOW_UNIQUENESS_RATIO:
                continue
            if uniq_a <= HIGH_UNIQUENESS_RATIO and uniq_b <= HIGH_UNIQUENESS_RATIO:
                continue

            pair_key = _unordered_key(table_a, col_a, table_b, col_b)
            prev = best.get(pair_key)
            if prev is not None and overlap <= prev["_overlap_ratio"]:
                continue

            from_table, from_column, to_table, to_column = _pick_direction(
                table_a, col_a, len(values_a), table_b, col_b, len(values_b)
            )
            if (from_table, from_column) == (table_a, col_a):
                vals_a, uniq_from = values_a, uniq_a
                vals_b, uniq_to = values_b, uniq_b
            else:
                vals_a, uniq_from = values_b, uniq_b
                vals_b, uniq_to = values_a, uniq_a
            best[pair_key] = {
                "from_table": from_table,
                "from_column": from_column,
                "to_table": to_table,
                "to_column": to_column,
                "cardinality": "unknown",
                "confidence": "inferred_from_data",
                "_overlap_ratio": overlap,
                "_unique_side_uniqueness": max(uniq_a, uniq_b),
                "_values_a": list(vals_a),
                "_values_b": list(vals_b),
                "_uniqueness_a": uniq_from,
                "_uniqueness_b": uniq_to,
            }

    return list(best.values())


def infer_relationships(
    conn: sqlite3.Connection,
    tables: list[str],
    *,
    overlap_threshold: float = OVERLAP_THRESHOLD,
    sample_limit: int = SAMPLE_LIMIT,
) -> list[dict[str, Any]]:
    """Return catalog-shaped relationships inferred from value overlap.

    Runs once at catalog extract (xlsx upload / schema sync), not per query.
    """
    return [
        _catalog_rel(rel)
        for rel in infer_relationship_candidates(
            conn,
            tables,
            overlap_threshold=overlap_threshold,
            sample_limit=sample_limit,
        )
    ]


def infer_relationship_candidates_from_path(
    sqlite_path: str,
    tables: Sequence[str],
    *,
    overlap_threshold: float = OVERLAP_THRESHOLD,
    sample_limit: int = SAMPLE_LIMIT,
) -> list[dict[str, Any]]:
    conn = sqlite3.connect(sqlite_path)
    try:
        return infer_relationship_candidates(
            conn,
            list(tables),
            overlap_threshold=overlap_threshold,
            sample_limit=sample_limit,
        )
    finally:
        conn.close()


def merge_with_declared(
    declared: Sequence[Mapping[str, Any]],
    inferred: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Keep declared FKs; add inferred edges that do not duplicate a pair."""
    merged = [dict(rel) for rel in declared]
    seen = {
        _unordered_key(
            str(rel["from_table"]),
            str(rel["from_column"]),
            str(rel["to_table"]),
            str(rel["to_column"]),
        )
        for rel in merged
    }
    for rel in inferred:
        key = _unordered_key(
            str(rel["from_table"]),
            str(rel["from_column"]),
            str(rel["to_table"]),
            str(rel["to_column"]),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(_catalog_rel(rel))
    return merged


_VERIFY_SYSTEM = (
    "You decide whether two spreadsheet columns are a real join key "
    "(the same entity, like a foreign key) or a coincidental overlap. "
    "Answer YES only if the columns clearly identify the same kind of thing "
    "(for example orders.customer_id referring to customers.customer_id, or "
    "order_items.related_order_ref referring to orders.order_id). "
    "Answer NO if the names refer to different entities (customer_id vs product_id), "
    "one side is a measure (quantity, amount, stock), patterns look like overlapping "
    "auto-increment integers across unrelated tables, or it is a shared category "
    "(region, status). If unsure, answer no. "
    "Reply with yes or no and one sentence of reasoning."
)


# Never interpolate raw cell values into this prompt. Only locally
# computed pattern descriptions from describe_column_pattern().
def _verification_prompt(candidate: Mapping[str, Any]) -> str:
    pattern_a = describe_column_pattern(
        candidate.get("_values_a") or [],
        uniqueness=candidate.get("_uniqueness_a"),
    )
    pattern_b = describe_column_pattern(
        candidate.get("_values_b") or [],
        uniqueness=candidate.get("_uniqueness_b"),
    )
    overlap_pct = round(float(candidate.get("_overlap_ratio", 0.0)) * 100)
    uniqueness = float(candidate.get("_unique_side_uniqueness", 0.0))
    table_a = candidate["from_table"]
    table_b = candidate["to_table"]
    name_a = candidate["from_column"]
    name_b = candidate["to_column"]
    return (
        f"Column A (table {table_a}, '{name_a}') has this value pattern: {pattern_a}. "
        f"Column B (table {table_b}, '{name_b}') has this value pattern: {pattern_b}. "
        f"They have {overlap_pct}% value overlap and {uniqueness:.2f} uniqueness "
        f"on the unique side. Based on the column names and these patterns "
        f"(not actual values), is this likely a genuine relationship between "
        f"these tables, or a coincidental match?"
    )


def _reply_is_yes(text: str) -> bool:
    return bool(_YES_RE.search(text or ""))


async def _llm_verify_candidate(candidate: dict[str, Any]) -> bool:
    from app.config import settings

    if not settings.OPENAI_API_KEY:
        logger.warning(
            "Skipping inferred relationship %s.%s -> %s.%s: OPENAI_API_KEY is not set",
            candidate.get("from_table"),
            candidate.get("from_column"),
            candidate.get("to_table"),
            candidate.get("to_column"),
        )
        return False

    try:
        import asyncio

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.RELATIONSHIP_VERIFY_MODEL_ID,
                messages=[
                    {"role": "system", "content": _VERIFY_SYSTEM},
                    {"role": "user", "content": _verification_prompt(candidate)},
                ],
                max_tokens=80,
                temperature=0,
            ),
            timeout=VERIFY_TIMEOUT_SECONDS,
        )
        content = (response.choices[0].message.content or "").strip()
        logger.info(
            "Relationship verify %s.%s -> %s.%s: %s",
            candidate.get("from_table"),
            candidate.get("from_column"),
            candidate.get("to_table"),
            candidate.get("to_column"),
            content,
        )
        return _reply_is_yes(content)
    except Exception:
        logger.exception(
            "Relationship verify failed for %s.%s -> %s.%s; dropping candidate",
            candidate.get("from_table"),
            candidate.get("from_column"),
            candidate.get("to_table"),
            candidate.get("to_column"),
        )
        return False


async def verify_relationship_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    verifier: RelationshipVerifier | None = None,
) -> list[dict[str, Any]]:
    """Keep candidates the verifier accepts. Fail closed on errors / missing key."""
    check = verifier if verifier is not None else _llm_verify_candidate
    kept: list[dict[str, Any]] = []
    for candidate in candidates:
        rel = dict(candidate)
        try:
            result = check(rel)
            if inspect.isawaitable(result):
                accepted = bool(await result)
            else:
                accepted = bool(result)
        except Exception:
            logger.exception(
                "Relationship verifier raised for %s.%s -> %s.%s; dropping",
                rel.get("from_table"),
                rel.get("from_column"),
                rel.get("to_table"),
                rel.get("to_column"),
            )
            accepted = False
        if accepted:
            kept.append(_catalog_rel(rel))
    return kept
