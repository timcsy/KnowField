"""T002/T003 [US1/US4]：WebSearchAdapter——SearchResult→Item 映射/去重；失敗向外拋。零外部呼叫。"""

import unittest
from datetime import datetime

from knowfield.search.websearch import SearchResult, StubWebSearch
from knowfield.sources.base import SourceUnavailable
from knowfield.sources.websearch_adapter import WebSearchAdapter


class TestWebSearchAdapter(unittest.TestCase):
    def test_fetch_maps_and_dedups(self):
        # StubWebSearch 每個 query 回固定 example.com/1、/2 → 兩 query 合併去重成 2 則
        adapter = WebSearchAdapter("web-ai-trends", StubWebSearch(), ["q1", "q2"])
        items = adapter.fetch(datetime(1970, 1, 1))
        urls = [i.url for i in items]
        self.assertEqual(len(urls), len(set(urls)))           # 依 url 去重
        self.assertTrue(all(i.url for i in items))            # 每則有原文連結
        self.assertTrue(all(i.title for i in items))          # title 映對
        self.assertTrue(all(i.content_hash for i in items))   # _finalize 補了 hash

    def test_field_mapping(self):
        class OneResult:
            def search(self, q, *, news=False, time_range=None):
                return [SearchResult("標題X", "https://a/x", "摘要Y")]
        items = WebSearchAdapter("web", OneResult(), ["q"]).fetch(datetime(1970, 1, 1))
        self.assertEqual(items[0].title, "標題X")
        self.assertEqual(items[0].url, "https://a/x")
        self.assertEqual(items[0].abstract, "摘要Y")

    def test_passes_news_and_time_range(self):
        seen = {}

        class Rec:
            def search(self, q, *, news=False, time_range=None):
                seen["news"] = news; seen["time_range"] = time_range
                return []
        WebSearchAdapter("web", Rec(), ["q"], news=True, time_range="week").fetch(
            datetime(1970, 1, 1))
        self.assertTrue(seen["news"])                         # 活水走 news 模式
        self.assertEqual(seen["time_range"], "week")

    def test_default_news_true(self):
        self.assertTrue(WebSearchAdapter("web", StubWebSearch(), ["q"]).news)  # 預設 news

    def test_search_failure_propagates(self):
        class Boom:
            def search(self, q, *, news=False, time_range=None):
                raise SourceUnavailable("搜尋掛了")
        adapter = WebSearchAdapter("web", Boom(), ["q"])
        with self.assertRaises(SourceUnavailable):            # 向外拋 → digest 攔成 missing
            adapter.fetch(datetime(1970, 1, 1))


if __name__ == "__main__":
    unittest.main()
