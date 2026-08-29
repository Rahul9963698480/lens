import os
import tempfile
import unittest
from pathlib import Path

import duckdb

os.environ.setdefault(
    "SUPABASE_DB_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)

from app.storage.xlsx_indexes import (
    apply_storage_optimizations,
    infer_primary_keys,
)
from app.storage.xlsx_ingest import workbook_to_duckdb
from openpyxl import Workbook


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


class XlsxIndexTests(unittest.TestCase):
    def test_primary_key_and_join_indexes_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "book.xlsx"
            duckdb_path = Path(tmp) / "out.duckdb"
            _write_workbook(
                xlsx_path,
                {
                    "customers": [
                        ["customer_id", "name"],
                        [1, "Alice"],
                        [2, "Bob"],
                    ],
                    "orders": [
                        ["order_id", "customer_id", "amount"],
                        [10, 1, 100],
                        [11, 2, 50],
                    ],
                },
            )
            tables = workbook_to_duckdb(xlsx_path, duckdb_path)
            conn = duckdb.connect(str(duckdb_path))
            try:
                pks = infer_primary_keys(conn, tables)
                self.assertIn("customers", pks)
                self.assertIn("orders", pks)
                apply_storage_optimizations(
                    conn,
                    [
                        {
                            "from_table": "orders",
                            "from_column": "customer_id",
                            "to_table": "customers",
                            "to_column": "customer_id",
                        }
                    ],
                    tables=tables,
                )
                indexes = {
                    row[0]
                    for row in conn.execute(
                        "SELECT index_name FROM duckdb_indexes()"
                    ).fetchall()
                }
                self.assertTrue(any("customer_id" in name for name in indexes))
                self.assertTrue(any("pk_" in name or "order_id" in name for name in indexes))
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
