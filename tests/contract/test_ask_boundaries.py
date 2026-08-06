"""T021 [US3]：誠實邊界——查無說無不杜撰；後端失敗友善繁中、無堆疊。"""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from knowfield.backends.openai_api import OpenAIError
from knowfield.cli import ask_cmd
from knowfield.store.repository import Repository
from tests.rag_helpers import capture, make_entry, seed_digest, temp_db


class TestAskBoundaries(unittest.TestCase):
    def setUp(self):
        os.environ["KNOWFIELD_BACKEND"] = "offline"

    def test_empty_db_says_no_material_no_fabrication(self):
        db = temp_db()
        Repository(db).close()   # 空庫
        args = SimpleNamespace(db=db, question="任何問題", today=False, lang=None, k=None)
        rc, out = capture(ask_cmd.handle, args)
        self.assertEqual(rc, 0)
        self.assertIn("沒有相關材料", out)
        self.assertNotIn("來源：", out)          # 不產生任何來源

    def test_irrelevant_question_says_no_material(self):
        db = temp_db()
        repo = Repository(db)
        seed_digest(repo, "2026-07-23", [
            make_entry(1, "t", "https://a/1", "Agent memory", "agent memory retrieval")])
        repo.close()
        # 明顯無關、且門檻擋掉 → 查無相關
        args = SimpleNamespace(db=db, question="zzzz 完全無關的冷門詞 qqqq",
                               today=False, lang=None, k=None)
        rc, out = capture(ask_cmd.handle, args)
        self.assertEqual(rc, 0)
        self.assertIn("沒有相關材料", out)
        self.assertNotIn("來源：", out)

    def test_backend_failure_friendly_no_traceback(self):
        db = temp_db()
        repo = Repository(db)
        seed_digest(repo, "2026-07-23", [
            make_entry(1, "t", "https://a/1", "Agent", "agent memory")])
        repo.close()

        class Boom:
            def __init__(self, *a, **k):
                pass

            def answer(self, *a, **k):
                raise OpenAIError("模擬 403 allocation_quarantined")

        args = SimpleNamespace(db=db, question="agent", today=False, lang=None, k=None)
        with mock.patch("knowfield.cli.ask_cmd.RagService", Boom):
            rc, out = capture(ask_cmd.handle, args)
        self.assertEqual(rc, 1)
        self.assertIn("失敗", out)               # 友善繁中訊息
        self.assertNotIn("Traceback", out)       # 不噴堆疊


if __name__ == "__main__":
    unittest.main()
