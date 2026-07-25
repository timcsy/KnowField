"""T004 [US1]：StubWebSearch、ApiWebSearch 解析（可注入 poster）、失敗。"""

import unittest

from learnnews.search.websearch import ApiWebSearch, SearchResult, StubWebSearch
from learnnews.sources.base import SourceUnavailable


class TestWebSearch(unittest.TestCase):
    def test_stub_returns_results(self):
        rs = StubWebSearch().search("agent")
        self.assertTrue(len(rs) >= 1)
        self.assertTrue(all(isinstance(r, SearchResult) and r.url for r in rs))

    def test_api_parses_tavily_shape(self):
        fake = {"results": [
            {"title": "T1", "url": "https://a/1", "content": "內容一"},
            {"link": "https://a/2", "snippet": "內容二"},        # 欄位變體
            {"title": "無網址略過", "content": "x"},               # 無 url → 略過
        ]}
        seen = {}

        def poster(url, payload):
            seen.update(payload)
            return fake

        rs = ApiWebSearch("https://api.tavily.com/search", "mykey",
                          poster=poster).search("q")
        self.assertEqual(seen.get("api_key"), "mykey")         # 金鑰放 body（Tavily）
        self.assertEqual(seen.get("query"), "q")
        self.assertEqual([r.url for r in rs], ["https://a/1", "https://a/2"])
        self.assertEqual(rs[0].title, "T1")
        self.assertEqual(rs[1].title, "https://a/2")           # 無 title → 退回 url
        self.assertIn("內容一", rs[0].snippet)

    def test_api_failure_raises_source_unavailable(self):
        def boom(url, payload):
            raise SourceUnavailable("模擬逾時")
        with self.assertRaises(SourceUnavailable):
            ApiWebSearch("https://api.tavily.com/search", "k", poster=boom).search("q")

    def test_news_mode_payload(self):
        seen = {}

        def poster(url, payload):
            seen.update(payload)
            return {"results": []}
        api = ApiWebSearch("https://api.tavily.com/search", "k", poster=poster)
        api.search("q", news=True, time_range="week")
        self.assertEqual(seen.get("topic"), "news")            # news 模式 → topic=news
        self.assertEqual(seen.get("time_range"), "week")

    def test_general_mode_omits_news_params(self):
        seen = {}

        def poster(url, payload):
            seen.update(payload)
            return {"results": []}
        ApiWebSearch("https://api.tavily.com/search", "k", poster=poster).search("q")
        self.assertNotIn("topic", seen)                        # 一般搜尋 → 不送 topic/time_range
        self.assertNotIn("time_range", seen)

    def test_stub_accepts_news_kwargs(self):
        rs = StubWebSearch().search("q", news=True, time_range="day")   # 相容、忽略、不拋
        self.assertTrue(rs)


if __name__ == "__main__":
    unittest.main()
