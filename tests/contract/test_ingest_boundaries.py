"""T016 [US3]：抓取失敗 → 友善繁中、退出碼 1、無 traceback、KB 無半殘種子。"""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from learnnews.cli import ingest_cmd
from learnnews.store.repository import Repository
from tests.rag_helpers import capture, temp_db
from tests.seed_helpers import http_fail


class TestIngestBoundaries(unittest.TestCase):
    def setUp(self):
        os.environ["LEARNNEWS_BACKEND"] = "offline"
        self.db = temp_db()

    def test_fetch_failure_friendly_and_no_half_seed(self):
        args = SimpleNamespace(db=self.db, ref="1706.03762", explainer=False, lang=None)
        with mock.patch("learnnews.seed.fetch.default_http_get", http_fail):
            rc, out = capture(ingest_cmd.handle, args)
        self.assertEqual(rc, 1)
        self.assertIn("失敗", out)              # 友善繁中
        self.assertNotIn("Traceback", out)
        # 不寫半殘種子
        repo = Repository(self.db)
        self.assertEqual(repo.list_corpus_entries(), [])
        repo.close()


if __name__ == "__main__":
    unittest.main()
