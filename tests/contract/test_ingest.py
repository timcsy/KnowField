"""T008 [US1]：ingest 指令——離線假 http_get，成功印標題＋連結；重複→已在庫。"""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from learnnews.cli import ingest_cmd
from tests.rag_helpers import capture, temp_db
from tests.seed_helpers import http_arxiv


class TestIngestContract(unittest.TestCase):
    def setUp(self):
        os.environ["LEARNNEWS_BACKEND"] = "offline"
        self.db = temp_db()

    def _args(self, ref, explainer=False):
        return SimpleNamespace(db=self.db, ref=ref, explainer=explainer, lang=None)

    def test_ingest_success_prints_title_and_link(self):
        with mock.patch("learnnews.seed.fetch.default_http_get", http_arxiv):
            rc, out = capture(ingest_cmd.handle, self._args("1706.03762", explainer=True))
        self.assertEqual(rc, 0)
        self.assertIn("已收進知識庫", out)
        self.assertIn("解說文", out)
        self.assertIn("arxiv.org/abs/1706.03762", out)   # 原文連結（溯源）

    def test_duplicate_says_exists(self):
        with mock.patch("learnnews.seed.fetch.default_http_get", http_arxiv):
            capture(ingest_cmd.handle, self._args("1706.03762"))
            rc, out = capture(ingest_cmd.handle, self._args("arXiv:1706.03762v5"))
        self.assertEqual(rc, 0)
        self.assertIn("已在庫", out)


if __name__ == "__main__":
    unittest.main()
