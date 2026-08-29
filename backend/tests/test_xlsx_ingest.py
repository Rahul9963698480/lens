import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import duckdb
from openpyxl import Workbook

from app.storage.xlsx_ingest import (
    XlsxIngestError,
    sanitize_identifier,
    unique_identifier,
    workbook_to_duckdb,
)


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


class SanitizeIdentifierTests(unittest.TestCase):
    def test_lowercase_and_underscores(self) -> None:
        self.assertEqual(sanitize_identifier("Sales Data"), "sales_data")

    def test_special_chars_and_leading_digit(self) -> None:
        self.assertEqual(sanitize_identifier("2024 Orders!"), "col_2024_orders")

    def test_unique_suffix(self) -> None:
        used: set[str] = set()
        self.assertEqual(unique_identifier("sheet", used), "sheet")
        self.assertEqual(unique_identifier("sheet", used), "sheet_2")


class WorkbookToDuckdbTests(unittest.TestCase):
    def test_two_sheets_types_and_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "sales.xlsx"
            duckdb_path = Path(tmp) / "out.duckdb"
            _write_workbook(
                xlsx_path,
                {
                    "Sales Data": [
                        ["qty", "amount", "name"],
                        [1, 10.5, "alpha"],
                        [2, 20.0, "beta"],
                    ],
                    "Orders!": [
                        ["order_date", "note"],
                        [date(2024, 1, 15), "first"],
                        [datetime(2024, 2, 1, 13, 30, 0), "second"],
                    ],
                },
            )
            tables = workbook_to_duckdb(xlsx_path, duckdb_path)
            self.assertEqual(tables, ["sales_data", "orders"])

            conn = duckdb.connect(str(duckdb_path), read_only=True)
            try:
                sales_info = conn.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'sales_data'
                    ORDER BY ordinal_position
                    """
                ).fetchall()
                types = {row[0]: row[1] for row in sales_info}
                self.assertEqual(types["qty"], "BIGINT")
                self.assertEqual(types["amount"], "DOUBLE")
                self.assertIn(types["name"], ("VARCHAR", "STRING"))

                qty_rows = conn.execute(
                    "SELECT qty FROM sales_data ORDER BY qty"
                ).fetchall()
                self.assertEqual([r[0] for r in qty_rows], [1, 2])
            finally:
                conn.close()

    def test_empty_workbook_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "empty.xlsx"
            duckdb_path = Path(tmp) / "out.duckdb"
            _write_workbook(xlsx_path, {"Empty": []})
            with self.assertRaises(XlsxIngestError):
                workbook_to_duckdb(xlsx_path, duckdb_path)
            self.assertFalse(duckdb_path.exists())

    def test_rejects_non_xlsx_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            path.write_text("a,b\n1,2\n", encoding="utf-8")
            with self.assertRaises(XlsxIngestError):
                workbook_to_duckdb(path, Path(tmp) / "out.duckdb")


if __name__ == "__main__":
    unittest.main()
