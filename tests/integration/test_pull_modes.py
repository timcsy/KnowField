"""T008：--raw 零生成文字（情境 B/SC-007）＋缺漏（F）＋冷門空（G）。"""

import unittest

from learnnews.cli.pull_cmd import run_pull
from learnnews.cli.pull_render import render
from tests.helpers import FakeAdapter, make_item


class TestPullModes(unittest.TestCase):
    def test_raw_produces_no_article(self):
        item = make_item("agent 規劃", external_id="1", url="https://a/1")
        result = run_pull([FakeAdapter("s", [item])], "agent", with_summary=False)
        for e in result.entries:
            self.assertIsNone(e.article)   # 未生成任何文字（未呼叫 LLM）

    def test_missing_source_recorded(self):
        good = make_item("agent 規劃", external_id="1", url="https://a/1")
        result = run_pull(
            [FakeAdapter("good", [good]), FakeAdapter("flaky", [], fail=True)], "agent")
        self.assertIn("flaky", result.missing_sources)
        self.assertEqual(len(result.entries), 1)

    def test_empty_cold_topic(self):
        item = make_item("貓咪攝影日常", external_id="1", url="https://a/1")
        result = run_pull([FakeAdapter("s", [item])], "量子重力理論")
        self.assertTrue(result.is_empty)
        out = render(result, "terminal")
        self.assertIn("查無", out)


if __name__ == "__main__":
    unittest.main()
