import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault(
    "SUPABASE_DB_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)

from openpyxl import Workbook

from app.storage.xlsx_ingest import workbook_to_sqlite
from app.storage.xlsx_relationships import (
    _reply_is_yes,
    _verification_prompt,
    describe_column_pattern,
    infer_relationship_candidates,
    infer_relationships,
    merge_with_declared,
    verify_relationship_candidates,
)

_SQL_GENERATOR = Path(__file__).resolve().parents[1] / "app" / "agent" / "sql_generator.py"
_ASSETS = Path(__file__).resolve().parents[1] / "app" / "assests"


def _write_workbook(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    wb = Workbook()
    default = wb.active
    first = True
    for name, rows in sheets.items():
        ws = default if first else wb.create_sheet(title=name)
        if first:
            ws.title = name
            first = False
        for row in rows:
            ws.append(row)
    wb.save(path)


def _unordered_pair(rel: dict) -> frozenset[tuple[str, str]]:
    return frozenset(
        (
            (rel["from_table"], rel["from_column"]),
            (rel["to_table"], rel["to_column"]),
        )
    )


def _infer_sheets(sheets: dict[str, list[list[object]]]) -> tuple[list[str], list[dict]]:
    with tempfile.TemporaryDirectory() as tmp:
        xlsx_path = Path(tmp) / "book.xlsx"
        sqlite_path = Path(tmp) / "out.sqlite"
        _write_workbook(xlsx_path, sheets)
        tables = workbook_to_sqlite(xlsx_path, sqlite_path)
        conn = sqlite3.connect(str(sqlite_path))
        try:
            rels = infer_relationships(conn, tables)
        finally:
            conn.close()
        return tables, rels


def _candidates_for_sheets(
    sheets: dict[str, list[list[object]]],
) -> tuple[list[str], list[dict]]:
    with tempfile.TemporaryDirectory() as tmp:
        xlsx_path = Path(tmp) / "book.xlsx"
        sqlite_path = Path(tmp) / "out.sqlite"
        _write_workbook(xlsx_path, sheets)
        tables = workbook_to_sqlite(xlsx_path, sqlite_path)
        conn = sqlite3.connect(str(sqlite_path))
        try:
            candidates = infer_relationship_candidates(conn, tables)
        finally:
            conn.close()
        return tables, candidates


def _openai_key_configured() -> bool:
    try:
        from app.config import settings

        return bool(settings.OPENAI_API_KEY)
    except Exception:
        return bool(os.environ.get("OPENAI_API_KEY"))


_CUSTOMERS_ORDERS = {
    "Customers": [
        ["customer_id", "name"],
        ["C1", "Alice"],
        ["C2", "Bob"],
        ["C3", "Cara"],
    ],
    "Orders": [
        ["order_id", "customer_id", "amount"],
        ["O1", "C1", 10.0],
        ["O2", "C2", 20.0],
        ["O3", "C1", 11.0],
        ["O4", "C3", 15.0],
        ["O5", "C2", 22.0],
    ],
}

_RENAMED_ORDER_REF = {
    "Orders": [
        ["order_id", "customer_id"],
        ["O1", "C1"],
        ["O2", "C2"],
        ["O3", "C3"],
    ],
    "Order Items": [
        ["related_order_ref", "product"],
        ["O1", "Widget"],
        ["O2", "Gadget"],
        ["O3", "Gizmo"],
        ["O1", "Bolt"],
    ],
}

_EMPLOYEE_CODE_VS_EMP_ID = {
    "Employees": [
        ["Employee Code", "name"],
        ["E-1001", "Ada"],
        ["E-1002", "Ben"],
        ["E-1003", "Cara"],
        ["E-1004", "Dee"],
        ["E-1005", "Eve"],
    ],
    "Payroll": [
        ["Emp ID", "amount"],
        ["E-1001", 10.0],
        ["E-1002", 20.0],
        ["E-1003", 11.0],
        ["E-1001", 12.0],
        ["E-1004", 15.0],
        ["E-1005", 18.0],
        ["E-1002", 22.0],
    ],
}

_EMPLOYEE_CODE_PAIR = frozenset(
    (("employees", "employee_code"), ("payroll", "emp_id"))
)


def _candidates_from_xlsx(xlsx: Path) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        sqlite_path = Path(tmp) / "out.sqlite"
        tables = workbook_to_sqlite(xlsx, sqlite_path)
        conn = sqlite3.connect(str(sqlite_path))
        try:
            return infer_relationship_candidates(conn, tables)
        finally:
            conn.close()


class InferRelationshipsTests(unittest.TestCase):
    def test_rejects_store_name_and_region_region(self) -> None:
        tables, rels = _infer_sheets(
            {
                "Sales Data": [
                    ["store", "name", "region", "amount"],
                    ["S1", "Widget", "West", 10.5],
                    ["S2", "Gadget", "East", 20.0],
                    ["S3", "Gizmo", "Central", 15.0],
                    ["S1", "Widget", "West", 11.0],
                    ["S2", "Gadget", "East", 22.0],
                    ["S3", "Gizmo", "Central", 16.0],
                ],
                "Stores": [
                    ["name", "region", "amount"],
                    ["Northgate", "West", 10.5],
                    ["Riverside", "East", 20.0],
                    ["Harbor", "Central", 15.0],
                    ["Westside", "West", 12.0],
                    ["Eastend", "East", 18.0],
                    ["Midtown", "Central", 14.0],
                ],
            }
        )
        self.assertEqual(tables, ["sales_data", "stores"])
        pairs = {_unordered_pair(r) for r in rels}
        self.assertNotIn(
            frozenset((("sales_data", "store"), ("stores", "name"))),
            pairs,
        )
        self.assertNotIn(
            frozenset((("sales_data", "region"), ("stores", "region"))),
            pairs,
        )
        self.assertNotIn(
            frozenset((("sales_data", "amount"), ("stores", "amount"))),
            pairs,
        )

    def test_rejects_low_cardinality_region_overlap(self) -> None:
        regions = ["West", "East", "Central"]
        employee_rows: list[list[object]] = [["name", "region"]]
        sales_rows: list[list[object]] = [["store", "region", "amount"]]
        for i in range(12):
            region = regions[i % 3]
            employee_rows.append([f"Emp{i}", region])
            sales_rows.append([f"S{i % 4}", region, float(i)])

        _tables, rels = _infer_sheets(
            {"Employees": employee_rows, "Sales Data": sales_rows}
        )
        pairs = {_unordered_pair(r) for r in rels}
        self.assertNotIn(
            frozenset((("employees", "region"), ("sales_data", "region"))),
            pairs,
        )
        self.assertEqual(rels, [])

    def test_proposes_customer_id_when_one_side_is_unique(self) -> None:
        tables, rels = _infer_sheets(_CUSTOMERS_ORDERS)
        self.assertEqual(tables, ["customers", "orders"])
        pairs = {_unordered_pair(r) for r in rels}
        customer_pair = frozenset(
            (("customers", "customer_id"), ("orders", "customer_id"))
        )
        self.assertIn(customer_pair, pairs)
        matches = [r for r in rels if _unordered_pair(r) == customer_pair]
        self.assertEqual(len(matches), 1)
        rel = matches[0]
        self.assertEqual(rel["cardinality"], "unknown")
        self.assertEqual(rel["confidence"], "inferred_from_data")
        self.assertNotIn("overlap_ratio", rel)
        self.assertNotIn("_overlap_ratio", rel)

    def test_proposes_renamed_order_ref_without_name_matching(self) -> None:
        tables, rels = _infer_sheets(_RENAMED_ORDER_REF)
        self.assertEqual(tables, ["orders", "order_items"])
        pair = frozenset(
            (("orders", "order_id"), ("order_items", "related_order_ref"))
        )
        self.assertIn(pair, {_unordered_pair(r) for r in rels})

    def test_proposes_employee_code_vs_emp_id(self) -> None:
        tables, rels = _infer_sheets(_EMPLOYEE_CODE_VS_EMP_ID)
        self.assertEqual(tables, ["employees", "payroll"])
        self.assertIn(_EMPLOYEE_CODE_PAIR, {_unordered_pair(r) for r in rels})

    def test_merge_skips_declared_pair(self) -> None:
        declared = [
            {
                "from_table": "sales_data",
                "from_column": "region",
                "to_table": "stores",
                "to_column": "region",
                "cardinality": "many_to_one",
                "confidence": "declared",
            }
        ]
        inferred = [
            {
                "from_table": "sales_data",
                "from_column": "region",
                "to_table": "stores",
                "to_column": "region",
                "cardinality": "unknown",
                "confidence": "inferred_from_data",
            }
        ]
        merged = merge_with_declared(declared, inferred)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["confidence"], "declared")

    def test_asset_related_workbook_detects_key_relationships(self) -> None:
        xlsx = _ASSETS / "related_workbook.xlsx"
        self.assertTrue(xlsx.exists(), f"missing asset {xlsx}")
        with tempfile.TemporaryDirectory() as tmp:
            sqlite_path = Path(tmp) / "out.sqlite"
            tables = workbook_to_sqlite(xlsx, sqlite_path)
            conn = sqlite3.connect(str(sqlite_path))
            try:
                rels = infer_relationships(conn, tables)
            finally:
                conn.close()

        involved = {r["from_column"] for r in rels} | {r["to_column"] for r in rels}
        for key in ("customer_id", "product_id", "order_id"):
            self.assertIn(key, involved, f"expected {key} relationship in {rels}")

    def test_asset_unrelated_workbook_rejects_region(self) -> None:
        xlsx = _ASSETS / "unrelated_workbook.xlsx"
        self.assertTrue(xlsx.exists(), f"missing asset {xlsx}")
        with tempfile.TemporaryDirectory() as tmp:
            sqlite_path = Path(tmp) / "out.sqlite"
            tables = workbook_to_sqlite(xlsx, sqlite_path)
            conn = sqlite3.connect(str(sqlite_path))
            try:
                rels = infer_relationships(conn, tables)
            finally:
                conn.close()

        pairs = {_unordered_pair(r) for r in rels}
        self.assertNotIn(
            frozenset((("employees", "region"), ("sales_data", "region"))),
            pairs,
        )
        for rel in rels:
            cols = {rel["from_column"], rel["to_column"]}
            self.assertFalse(
                cols == {"region"},
                f"unexpected region relationship: {rel}",
            )


class VerifyRelationshipsTests(unittest.IsolatedAsyncioTestCase):
    def test_reply_is_yes_parsing(self) -> None:
        self.assertTrue(_reply_is_yes("Yes. These look like foreign keys."))
        self.assertTrue(_reply_is_yes("yes"))
        self.assertFalse(_reply_is_yes("No. Shared category, not a join key."))
        self.assertFalse(_reply_is_yes(""))

    async def test_mock_verifier_false_drops_candidate(self) -> None:
        _tables, candidates = _candidates_for_sheets(_CUSTOMERS_ORDERS)
        self.assertGreater(len(candidates), 0)
        kept = await verify_relationship_candidates(
            candidates, verifier=lambda _c: False
        )
        self.assertEqual(kept, [])

    async def test_mock_verifier_true_keeps_catalog_shaped(self) -> None:
        _tables, candidates = _candidates_for_sheets(_CUSTOMERS_ORDERS)
        self.assertGreater(len(candidates), 0)
        kept = await verify_relationship_candidates(
            candidates, verifier=lambda _c: True
        )
        self.assertEqual(len(kept), len(candidates))
        for rel in kept:
            self.assertNotIn("_overlap_ratio", rel)
            self.assertNotIn("_values_a", rel)
            self.assertNotIn("_values_b", rel)
            self.assertEqual(rel["confidence"], "inferred_from_data")

    async def test_pipeline_accept_then_merge_matches_get_schema(self) -> None:
        _tables, candidates = _candidates_for_sheets(_CUSTOMERS_ORDERS)
        kept = await verify_relationship_candidates(
            candidates, verifier=lambda _c: True
        )
        merged = merge_with_declared([], kept)
        pairs = {_unordered_pair(r) for r in merged}
        self.assertIn(
            frozenset((("customers", "customer_id"), ("orders", "customer_id"))),
            pairs,
        )

        dropped = await verify_relationship_candidates(
            candidates, verifier=lambda _c: False
        )
        self.assertEqual(merge_with_declared([], dropped), [])

    @unittest.skipUnless(_openai_key_configured(), "OPENAI_API_KEY is not configured")
    async def test_llm_keeps_renamed_genuine_key(self) -> None:
        _tables, candidates = _candidates_for_sheets(_RENAMED_ORDER_REF)
        pair = frozenset(
            (("orders", "order_id"), ("order_items", "related_order_ref"))
        )
        self.assertIn(pair, {_unordered_pair(c) for c in candidates})
        kept = await verify_relationship_candidates(candidates)
        self.assertIn(pair, {_unordered_pair(r) for r in kept})

    @unittest.skipUnless(_openai_key_configured(), "OPENAI_API_KEY is not configured")
    async def test_llm_related_workbook_keeps_key_ids(self) -> None:
        xlsx = _ASSETS / "related_workbook.xlsx"
        self.assertTrue(xlsx.exists(), f"missing asset {xlsx}")
        candidates = _candidates_from_xlsx(xlsx)
        kept = await verify_relationship_candidates(candidates)
        involved = {r["from_column"] for r in kept} | {r["to_column"] for r in kept}
        for key in ("customer_id", "product_id", "order_id"):
            self.assertIn(key, involved, f"expected {key} relationship in {kept}")

    @unittest.skipUnless(_openai_key_configured(), "OPENAI_API_KEY is not configured")
    async def test_llm_keeps_employee_code_vs_emp_id(self) -> None:
        """Pattern-only prompt should still catch same-meaning different names.

        Live check: related_workbook still keeps customer_id/product_id/order_id;
        Employee Code vs Emp ID (E-####) is kept; related_order_ref vs order_id
        is kept. Region on unrelated_workbook never reaches this step (cardinality
        gate). No miss observed on these cases versus the old raw-value prompt.

        Remaining tradeoff: genuine joins are more likely to be dropped when
        names are unrelated AND the format is generic sequential integers with
        no shared prefix. Distinctive formats (E-####, O#) and aligned names
        remain the reliable cases.
        """
        _tables, candidates = _candidates_for_sheets(_EMPLOYEE_CODE_VS_EMP_ID)
        self.assertIn(_EMPLOYEE_CODE_PAIR, {_unordered_pair(c) for c in candidates})
        kept = await verify_relationship_candidates(candidates)
        self.assertIn(_EMPLOYEE_CODE_PAIR, {_unordered_pair(r) for r in kept})


class DescribeColumnPatternTests(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(describe_column_pattern([]), "empty")
        self.assertEqual(describe_column_pattern([None, "  "]), "empty")

    def test_digit_ids_use_width_bucket_not_extrema(self) -> None:
        text = describe_column_pattern([10001, 10002, 23456], uniqueness=1.0)
        self.assertIn("5-digit numeric IDs", text)
        self.assertIn("no duplicates", text)
        self.assertIn("range 10000-99999", text)
        self.assertNotIn("10001", text)
        self.assertNotIn("23456", text)

    def test_prefixed_numeric_ids(self) -> None:
        text = describe_column_pattern(["E-1001", "E-1002", "E-2200"], uniqueness=1.0)
        self.assertIn("format similar to 'E-####'", text)
        self.assertNotIn("E-1001", text)
        self.assertNotIn("E-2200", text)

    def test_emails_do_not_echo_addresses(self) -> None:
        addr_a = "alice.secret.token@example.com"
        addr_b = "carol.hidden.value@example.com"
        text = describe_column_pattern([addr_a, addr_b], uniqueness=1.0)
        self.assertIn("email-like strings", text)
        self.assertNotIn(addr_a, text)
        self.assertNotIn(addr_b, text)

    def test_duplicate_phrase_from_uniqueness(self) -> None:
        text = describe_column_pattern(["E-1001", "E-1002"], uniqueness=0.5)
        self.assertIn("some duplicates", text)


class VerificationPromptPrivacyTests(unittest.TestCase):
    def test_prompt_contains_no_raw_cell_values(self) -> None:
        raw_a = ["EMP-ZX9Q42", "EMP-ZX9Q43", "EMP-ZX9Q44"]
        raw_b = [
            "alice.secret.token@example.com",
            "carol.hidden.value@example.com",
            "drew.private.mail@example.com",
        ]
        candidate = {
            "from_table": "payroll",
            "from_column": "emp_id",
            "to_table": "staff",
            "to_column": "employee_code",
            "_overlap_ratio": 0.95,
            "_unique_side_uniqueness": 1.0,
            "_values_a": raw_a,
            "_values_b": raw_b,
            "_uniqueness_a": 1.0,
            "_uniqueness_b": 1.0,
        }
        prompt = _verification_prompt(candidate)
        self.assertIn("value pattern", prompt)
        self.assertNotIn("Sample values", prompt)
        for value in raw_a + raw_b:
            self.assertNotIn(
                str(value),
                prompt,
                f"raw cell {value!r} leaked into prompt: {prompt}",
            )

    def test_inferred_candidate_prompt_omits_sheet_values(self) -> None:
        _tables, candidates = _candidates_for_sheets(_CUSTOMERS_ORDERS)
        self.assertGreater(len(candidates), 0)
        forbidden = {"C1", "C2", "C3", "O1", "O2", "O3", "O4", "O5", "Alice", "Bob", "Cara"}
        for candidate in candidates:
            self.assertNotIn("_sample_values", candidate)
            prompt = _verification_prompt(candidate)
            for value in forbidden:
                self.assertNotIn(
                    value,
                    prompt,
                    f"{value!r} leaked into prompt: {prompt}",
                )


class AgentPromptTests(unittest.TestCase):
    def test_join_instruction_forbids_invented_joins(self) -> None:
        text = _SQL_GENERATOR.read_text(encoding="utf-8")
        self.assertIn("AGENT_INSTRUCTIONS", text)
        self.assertIn(
            "You may ONLY join two tables using a relationship explicitly present",
            text,
        )
        self.assertIn("from introspect_schema", text)
        self.assertIn("must NEVER join on a column pair just because the names", text)
        self.assertIn("must NEVER invent a join to force an answer", text)
        self.assertIn("relationship exists in the schema for this comparison", text)
        self.assertIn("NEVER write JOIN", text)
        self.assertIn("relationships array is empty", text)
        self.assertIn("do not emit a SQL", text)
        self.assertIn("no SQL and no JOIN", text)


if __name__ == "__main__":
    unittest.main()
