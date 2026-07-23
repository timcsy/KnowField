"""T007：原文連結 100%（情境 D）＋散文消化（spec 003 後不再封頂）。"""

import unittest

from learnnews.cli.pull_cmd import run_pull
from tests.helpers import FakeAdapter, make_item


class TestPullQuality(unittest.TestCase):
    def test_every_entry_has_source_link(self):
        items = [make_item(f"agent 研究 {i}", external_id=str(i), url=f"https://a/{i}")
                 for i in range(3)]
        result = run_pull([FakeAdapter("s", items)], "agent")
        self.assertTrue(result.entries)
        for e in result.entries:
            self.assertTrue(e.item.url.strip())      # SC-002 100% 溯源

    def test_default_article_present_with_source(self):
        item = make_item("agent 記憶機制", external_id="1", url="https://a/1",
                         abstract="agent 記憶研究前文。")
        result = run_pull([FakeAdapter("s", [item])], "agent")
        a = result.entries[0].article
        self.assertIsNotNone(a)
        self.assertTrue(a.body.strip())
        self.assertEqual(a.source_url, "https://a/1")  # 一鍵原文

    def test_item_without_link_excluded(self):
        from learnnews.models import Item
        no_link = Item(source_id="s", external_id="9", title="agent 無連結",
                       url="", content_hash="h9")
        good = make_item("agent 有連結", external_id="10", url="https://a/10")
        result = run_pull([FakeAdapter("s", [no_link, good])], "agent")
        urls = [e.item.url for e in result.entries]
        self.assertNotIn("", urls)
        self.assertIn("https://a/10", urls)


if __name__ == "__main__":
    unittest.main()
