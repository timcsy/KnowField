"""T009：PullService 擴展→去重→依主題排序→(可選)摘要。"""

import unittest

from learnnews.pull.service import PullService
from learnnews.summarize.summarizer import count_sentences
from tests.helpers import FakeAdapter, make_item


class TestPullService(unittest.TestCase):
    def setUp(self):
        self.svc = PullService()

    def test_ranks_by_topic_and_filters(self):
        items = [
            make_item("agent 規劃記憶", external_id="1", url="https://a/1"),
            make_item("貓咪攝影教學", external_id="2", url="https://a/2"),
        ]
        result = self.svc.pull("agent", [FakeAdapter("s", items)])
        titles = [e.item.title for e in result.entries]
        self.assertIn("agent 規劃記憶", titles)
        self.assertNotIn("貓咪攝影教學", titles)

    def test_dedup_across_sources(self):
        a = make_item("agent 規劃", external_id="dup", url="https://a")
        b = make_item("agent 規劃", external_id="dup", url="https://b")
        result = self.svc.pull("agent", [FakeAdapter("s1", [a]), FakeAdapter("s2", [b])])
        self.assertEqual(len(result.entries), 1)

    def test_with_article_default(self):
        item = make_item("agent 記憶", external_id="1", url="https://a/1")
        result = self.svc.pull("agent", [FakeAdapter("s", [item])])
        self.assertIsNotNone(result.entries[0].article)
        self.assertTrue(result.entries[0].article.body.strip())

    def test_raw_no_article(self):
        item = make_item("agent 記憶", external_id="1", url="https://a/1")
        result = self.svc.pull("agent", [FakeAdapter("s", [item])], with_summary=False)
        self.assertIsNone(result.entries[0].article)

    def test_limit_and_truncation(self):
        # 彼此不同的 agent 相關標題（避免語義去重合併）
        words = ["規劃", "記憶", "工具", "協作", "除錯", "評測", "安全", "對話", "檢索", "模擬"]
        items = [make_item(f"agent {w}", external_id=str(i), url=f"https://a/{i}")
                 for i, w in enumerate(words)]
        result = self.svc.pull("agent", [FakeAdapter("s", items)], limit=3)
        self.assertEqual(len(result.entries), 3)
        self.assertEqual(result.truncated_count, 7)

    def test_missing_source_not_silent(self):
        good = make_item("agent 規劃", external_id="1", url="https://a/1")
        result = self.svc.pull(
            "agent", [FakeAdapter("good", [good]), FakeAdapter("bad", [], fail=True)])
        self.assertIn("bad", result.missing_sources)
        self.assertEqual(len(result.entries), 1)

    def test_empty_when_no_match(self):
        item = make_item("貓咪攝影", external_id="1", url="https://a/1")
        result = self.svc.pull("量子密碼學", [FakeAdapter("s", [item])])
        self.assertTrue(result.is_empty)


if __name__ == "__main__":
    unittest.main()
