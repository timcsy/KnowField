"""T047：`sources` 指令契約（list/enable/disable）。"""

import os
import tempfile
import unittest
from argparse import Namespace

from learnnews.cli import sources_cmd
from learnnews.store.repository import Repository


class TestCliSources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.db")

    def _run(self, action, source_id=None):
        args = Namespace(db=self.db, json=True, sources_action=action,
                         source_id=source_id)
        return sources_cmd.handle(args)

    def test_list_seeds_defaults(self):
        self.assertEqual(self._run("list"), 0)
        self.assertTrue(Repository(self.db).list_sources())  # 種入預設來源

    def test_disable_excludes_from_enabled(self):
        self._run("list")
        self._run("disable", source_id="arxiv-cs")
        enabled = [s.id for s in Repository(self.db).list_sources(enabled_only=True)]
        self.assertNotIn("arxiv-cs", enabled)


if __name__ == "__main__":
    unittest.main()
