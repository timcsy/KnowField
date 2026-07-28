"""spec 021：反逢迎的「值不值得」副手——純函式 worthit。

涵蓋：獵心得 query 角度（T001）、Stub 綜合引用證據（T002）、assess_worth 去重/無結果/失敗（T003）、
OpenAI 綜合＋邊界（T005）。全離線、零外部呼叫。
"""

import unittest

from learnnews.backends.openai_api import OpenAIError
from learnnews.search.websearch import SearchResult
from learnnews.search.worthit import (
    OpenAIWorthItSynthesizer,
    StubWorthItSynthesizer,
    assess_worth,
    worthit_queries,
)
from learnnews.sources.base import SourceUnavailable


class _FakeWebSearch:
    def __init__(self, results, *, sink=None, fail=False):
        self._results = results
        self._sink = sink
        self._fail = fail

    def search(self, query, *, news=False, time_range=None):
        if self._fail:
            raise SourceUnavailable("搜尋炸了")
        if self._sink is not None:
            self._sink.append((query, news))
        return list(self._results)


class TestWorthItQueries(unittest.TestCase):
    def test_multi_angle_not_generic(self):                      # T001
        qs = worthit_queries("Claude Opus 5")
        self.assertGreaterEqual(len(qs), 4)
        joined = " ".join(qs).lower()
        # 專打心得/批評/怎麼用，非只查通用名
        self.assertTrue(any("Claude Opus 5" in q for q in qs))
        self.assertTrue(any(k in joined for k in ("review", "評價", "心得")))
        self.assertTrue(any(k in joined for k in ("complaint", "缺點", "limitations", "值得")))
        self.assertTrue(any(k in joined for k in ("how to", "怎麼用")))
        self.assertNotIn("Claude Opus 5", [q.strip() for q in qs])  # 不是「只有通用名」那條

    def test_empty(self):                                        # T001
        self.assertEqual(worthit_queries("  "), [])


class TestStubSynthesizer(unittest.TestCase):
    def test_cites_evidence(self):                               # T002
        ev = [SearchResult("很棒", "https://a/1", "有人說好用"),
              SearchResult("很雷", "https://b/2", "有人說難搞")]
        out = StubWorthItSynthesizer().synthesize("某工具", ev)
        self.assertIn("某工具", out)
        self.assertIn("https://a/1", out)                        # 有引用可回核
        self.assertIn("https://b/2", out)


class TestAssessWorth(unittest.TestCase):
    def _ev(self):
        return [SearchResult("t1", "https://a/1", "s1"),
                SearchResult("t1 again", "https://a/1", "s1"),   # 重複 url
                SearchResult("t2", "https://b/2", "s2")]

    def test_dedup_and_synthesize(self):                         # T003
        sink = []
        v = assess_worth(_FakeWebSearch(self._ev(), sink=sink),
                         StubWorthItSynthesizer(), "某工具")
        self.assertFalse(v.no_material)
        urls = [s.url for s in v.sources]
        self.assertEqual(len(urls), len(set(urls)))              # 去重
        self.assertIn("https://a/1", urls)
        self.assertTrue(all(news is False for _, news in sink))  # 一般搜尋非 news

    def test_no_material(self):                                  # T003
        v = assess_worth(_FakeWebSearch([]), StubWorthItSynthesizer(), "冷門到爆的東西")
        self.assertTrue(v.no_material)

    def test_search_failure_raises(self):                        # T003
        with self.assertRaises(SourceUnavailable):
            assess_worth(_FakeWebSearch([], fail=True), StubWorthItSynthesizer(), "x")


class TestOpenAISynthesizer(unittest.TestCase):
    def test_calls_chat_returns_synthesis(self):                 # T005
        seen = {}

        def poster(base, path, key, payload):
            seen["path"] = path
            return {"choices": [{"message": {"content": "官方：…／獨立：…／用戶：…（https://a/1）"}}]}
        out = OpenAIWorthItSynthesizer("b", "k", "m", poster=poster).synthesize(
            "某工具", [SearchResult("t", "https://a/1", "s")])
        self.assertIn("用戶", out)
        self.assertEqual(seen["path"], "/chat/completions")

    def test_poster_failure_raises_openaierror(self):            # T005（教訓 3 邊界）
        def boom(*a, **k):
            raise RuntimeError("網路炸了")
        with self.assertRaises(OpenAIError):
            OpenAIWorthItSynthesizer("b", "k", "m", poster=boom).synthesize(
                "某工具", [SearchResult("t", "https://a/1", "s")])


if __name__ == "__main__":
    unittest.main()
