"""T013：`digest` 指令核心契約（run_digest）。"""

import unittest

from learnnews.cli.digest_cmd import run_digest
from learnnews.cli.render import render
from learnnews.models import InterestProfile
from learnnews.store.repository import Repository
from tests.helpers import FakeAdapter, make_item


class TestCliDigest(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")
        self.repo.save_interest_profile(InterestProfile(explicit_topics=["LLM 推理"]))

    def tearDown(self):
        self.repo.close()

    def test_digest_has_entries_with_links_and_capped_summary(self):
        item = make_item("LLM 推理 最佳化", external_id="2401.1",
                         url="https://arxiv.org/abs/2401.1")
        digest = run_digest(self.repo, [FakeAdapter("arxiv", [item])], "2026-07-23")
        self.assertFalse(digest.is_empty)
        for e in digest.entries:
            self.assertTrue(e.item.url)             # SC-003 原文連結
            self.assertIsNotNone(e.summary)

    def test_render_terminal_is_chinese(self):
        item = make_item("LLM 推理 教學", external_id="2401.2",
                         url="https://arxiv.org/abs/2401.2")
        digest = run_digest(self.repo, [FakeAdapter("arxiv", [item])], "2026-07-23")
        out = render(digest, "terminal")
        self.assertIn("每日分診匯整", out)
        self.assertIn("原文：", out)

    def test_json_output_valid(self):
        import json
        item = make_item("LLM 推理", external_id="2401.3", url="https://a/3")
        digest = run_digest(self.repo, [FakeAdapter("arxiv", [item])], "2026-07-23")
        parsed = json.loads(render(digest, "json"))
        self.assertEqual(parsed["date"], "2026-07-23")


if __name__ == "__main__":
    unittest.main()
