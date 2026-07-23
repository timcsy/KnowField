"""T005：`pull` 指令核心契約（run_pull）＋渲染。"""

import json
import unittest

from learnnews.cli.pull_cmd import run_pull
from learnnews.cli.pull_render import render
from tests.helpers import FakeAdapter, make_item


class TestCliPull(unittest.TestCase):
    def test_entries_have_links_and_default_summary(self):
        item = make_item("agent 規劃框架", external_id="1", url="https://arxiv.org/abs/1")
        result = run_pull([FakeAdapter("arxiv", [item])], "agent")
        self.assertFalse(result.is_empty)
        for e in result.entries:
            self.assertTrue(e.item.url)          # 溯源
            self.assertIsNotNone(e.summary)      # 預設附定位

    def test_raw_mode_no_generated_text(self):
        item = make_item("agent 規劃", external_id="1", url="https://a/1")
        result = run_pull([FakeAdapter("s", [item])], "agent", with_summary=False)
        out = render(result, "terminal", raw=True)
        self.assertIn("agent 規劃", out)         # 標題在
        self.assertIn("原文：", out)
        # 純原礦：不應出現「為何值得看」等生成欄位
        self.assertNotIn("為何值得看", out)

    def test_json_output(self):
        item = make_item("agent", external_id="1", url="https://a/1")
        result = run_pull([FakeAdapter("s", [item])], "agent")
        parsed = json.loads(render(result, "json"))
        self.assertEqual(parsed["topic"], "agent")
        self.assertIn("positioning", parsed["entries"][0])

    def test_json_raw_omits_positioning(self):
        item = make_item("agent", external_id="1", url="https://a/1")
        result = run_pull([FakeAdapter("s", [item])], "agent", with_summary=False)
        parsed = json.loads(render(result, "json", raw=True))
        self.assertNotIn("positioning", parsed["entries"][0])


if __name__ == "__main__":
    unittest.main()
