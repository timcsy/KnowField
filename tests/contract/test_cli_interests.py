"""T036：`interests` 指令契約（list/add/remove/set，經真實 CLI handle 與檔案 DB）。"""

import os
import tempfile
import unittest
from argparse import Namespace

from learnnews.cli import interests_cmd
from learnnews.store.repository import Repository


class TestCliInterests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.db")

    def _run(self, action, **kw):
        args = Namespace(db=self.db, json=False, interests_action=action,
                         topic=kw.get("topic"), topics=kw.get("topics"))
        return interests_cmd.handle(args)

    def test_add_then_list(self):
        self.assertEqual(self._run("add", topic="LLM 推理"), 0)
        self.assertEqual(self._run("add", topic="agent"), 0)
        topics = Repository(self.db).get_interest_profile().explicit_topics
        self.assertEqual(topics, ["LLM 推理", "agent"])

    def test_remove(self):
        self._run("set", topics=["A", "B", "C"])
        self._run("remove", topic="B")
        topics = Repository(self.db).get_interest_profile().explicit_topics
        self.assertEqual(topics, ["A", "C"])

    def test_set_overwrites_and_dedups(self):
        self._run("set", topics=["A", "A", "B"])
        topics = Repository(self.db).get_interest_profile().explicit_topics
        self.assertEqual(topics, ["A", "B"])


if __name__ == "__main__":
    unittest.main()
