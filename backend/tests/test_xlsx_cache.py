import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

os.environ.setdefault(
    "SUPABASE_DB_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)

from app.storage import xlsx_cache


class XlsxCacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        xlsx_cache._local_cache.clear()

    def tearDown(self) -> None:
        xlsx_cache._local_cache.clear()

    async def test_second_call_skips_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = str(Path(tmp) / "proj.sqlite")
            Path(local_path).write_bytes(b"sqlite")
            xlsx_cache.seed_local_cache("proj-1", local_path)

            download = AsyncMock()
            with patch("app.storage.xlsx_cache.download_file", download):
                first = await xlsx_cache.get_cached_local_path(
                    "proj-1", "xlsx-projects/proj-1.sqlite"
                )
                second = await xlsx_cache.get_cached_local_path(
                    "proj-1", "xlsx-projects/proj-1.sqlite"
                )

            self.assertEqual(first, local_path)
            self.assertEqual(second, local_path)
            download.assert_not_called()

    async def test_miss_downloads_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "xlsx_cache"
            cache_root.mkdir(parents=True, exist_ok=True)

            async def fake_download(_storage_path: str, local_path: str) -> None:
                Path(local_path).write_bytes(b"downloaded")

            download = AsyncMock(side_effect=fake_download)
            with (
                patch("app.storage.xlsx_cache.cache_dir", return_value=cache_root),
                patch("app.storage.xlsx_cache.download_file", download),
            ):
                first = await xlsx_cache.get_cached_local_path(
                    "proj-2", "xlsx-projects/proj-2.sqlite"
                )
                second = await xlsx_cache.get_cached_local_path(
                    "proj-2", "xlsx-projects/proj-2.sqlite"
                )

            self.assertEqual(Path(first).read_bytes(), b"downloaded")
            self.assertEqual(first, second)
            self.assertEqual(download.call_count, 1)

    def test_evict_removes_file_and_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "proj.sqlite"
            local_path.write_bytes(b"sqlite")
            xlsx_cache.seed_local_cache("proj-3", str(local_path))
            xlsx_cache.evict_local_cache("proj-3")
            self.assertNotIn("proj-3", xlsx_cache._local_cache)
            self.assertFalse(local_path.exists())


if __name__ == "__main__":
    unittest.main()
