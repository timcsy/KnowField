"""T012 [US1]：ask 指令契約——離線後端，累積問答回答＋列出來源。"""

import os
import unittest
from types import SimpleNamespace

from knowfield.cli import ask_cmd
from knowfield.store.repository import Repository
from tests.rag_helpers import capture, make_entry, seed_digest, temp_db


class TestAskContract(unittest.TestCase):
    def setUp(self):
        os.environ["KNOWFIELD_BACKEND"] = "offline"   # 明講離線，勝過 .env
        self.db = temp_db()
        repo = Repository(self.db)
        seed_digest(repo, "2026-07-23", [
            make_entry(1, "Agent paper", "https://a/agent", "Agent memory",
                       "agent memory retrieval systems"),
        ])
        repo.close()

    def test_ask_answers_and_lists_sources(self):
        args = SimpleNamespace(db=self.db, question="agent memory",
                               today=False, lang=None, k=None)
        rc, out = capture(ask_cmd.handle, args)
        self.assertEqual(rc, 0)
        self.assertIn("來源：", out)                 # 有來源清單
        self.assertIn("https://a/agent", out)        # 一鍵原文（溯源）


if __name__ == "__main__":
    unittest.main()
