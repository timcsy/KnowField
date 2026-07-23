"""T006：digest/pull 輸出散文（非列點）＋一鍵原文。"""

import unittest

from learnnews.cli.digest_cmd import run_digest
from learnnews.cli.pull_cmd import run_pull
from learnnews.cli.render import render as digest_render
from learnnews.cli.pull_render import render as pull_render
from learnnews.models import InterestProfile
from learnnews.store.repository import Repository
from tests.helpers import FakeAdapter, make_item


class TestCliArticle(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")
        self.repo.save_interest_profile(InterestProfile(explicit_topics=["agent"]))

    def tearDown(self):
        self.repo.close()

    def test_digest_renders_prose_and_source(self):
        item = make_item("agent 規劃", external_id="1", url="https://arxiv.org/abs/1",
                         abstract="agent 規劃的研究前文。")
        digest = run_digest(self.repo, [FakeAdapter("s", [item])], "2026-07-23")
        out = digest_render(digest, "markdown")
        self.assertIn("agent 規劃的研究前文", out)  # 散文內容
        self.assertIn("原文：https://arxiv.org/abs/1", out)  # 一鍵原文

    def test_pull_renders_prose_and_source(self):
        item = make_item("agent 記憶", external_id="2", url="https://a/2",
                         abstract="agent 記憶研究前文。")
        result = run_pull([FakeAdapter("s", [item])], "agent")
        out = pull_render(result, "markdown")
        self.assertIn("agent 記憶研究前文", out)
        self.assertIn("原文：https://a/2", out)


if __name__ == "__main__":
    unittest.main()
