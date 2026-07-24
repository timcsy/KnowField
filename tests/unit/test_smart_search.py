"""T003/T004 [US1/US2]：SmartSearch.run——排序、passages 轉接、grounded 降級、no_material。

全離線、零外部呼叫（注入 web_search／embedder／answerer／fetch stub）。
"""

import unittest

from learnnews.models import Item
from learnnews.search.smart import SmartResult, SmartSearch
from learnnews.search.websearch import SearchResult


class KwEmbedder:
    """關鍵字嵌入：含 MATCH → [1,0]，否則 [0,1]。令含 MATCH 的結果與 query 最相關。"""

    def embed(self, text):
        return [1.0, 0.0] if "MATCH" in (text or "") else [0.0, 1.0]


class FixedAnswerer:
    def __init__(self, text):
        self._text = text
        self.seen = None

    def answer(self, question, passages, lang):
        self.seen = (question, passages, lang)
        return self._text


def _fetch_ok(url):
    return Item(source_id="s", external_id="", title="抓到標題",
                url=url, abstract=f"內文 body for {url}")


def _results():
    return [
        SearchResult("普通一", "https://a/1", "snippet 1"),
        SearchResult("MATCH 命中", "https://a/2", "snippet 2 MATCH"),
        SearchResult("普通三", "https://a/3", "snippet 3"),
    ]


class TestSmartSearchRun(unittest.TestCase):
    def _make(self, answerer=None, fetch=_fetch_ok, results=None):
        rs = _results() if results is None else results
        ws = type("WS", (), {"search": staticmethod(lambda q: rs)})()
        return SmartSearch(web_search=ws, embedder=KwEmbedder(),
                           answerer=answerer or FixedAnswerer("整理[1][2]"),
                           fetch=fetch, top_n=4)

    def test_ranks_most_relevant_first(self):
        out = self._make().run("MATCH query")
        self.assertIsInstance(out, SmartResult)
        self.assertEqual(out.results[0].url, "https://a/2")   # 含 MATCH → 排第一

    def test_passages_adapter(self):
        ans = FixedAnswerer("整理[1]")
        self._make(answerer=ans).run("MATCH query")
        q, passages, lang = ans.seen
        self.assertEqual(lang, "繁體中文")
        p0 = passages[0]
        self.assertEqual(p0.entry_id, 1)                      # 序位＝排序後
        self.assertEqual(p0.url, "https://a/2")               # 最相關那則
        self.assertIn("內文 body", p0.body)                    # body＝抓到的內文

    def test_returns_full_ranked_results_and_sources(self):
        out = self._make().run("MATCH query")
        self.assertEqual(len(out.results), 3)                 # 回排序後完整清單
        self.assertFalse(out.no_material)
        self.assertEqual(out.sources[0].n, 1)
        self.assertEqual(out.sources[0].url, "https://a/2")

    def test_fetch_failure_degrades_to_snippet(self):
        def _fetch_one_fails(url):
            if url == "https://a/2":
                raise RuntimeError("抓不到")
            return _fetch_ok(url)
        ans = FixedAnswerer("整理[1]")
        out = self._make(answerer=ans, fetch=_fetch_one_fails).run("MATCH query")
        self.assertIsInstance(out, SmartResult)               # 不拋、不整段壞
        p0 = ans.seen[1][0]
        self.assertIn("MATCH", p0.body)                       # a/2 抓不到 → 退回 snippet

    def test_no_material_suppresses_sources(self):
        out = self._make(answerer=FixedAnswerer("沒有相關材料。")).run("MATCH query")
        self.assertTrue(out.no_material)
        self.assertEqual(out.sources, [])                     # 說沒材料就不列來源（教訓 7）

    def test_overview_error_keeps_results_when_answerer_raises(self):
        def boom(question, passages, lang):
            raise RuntimeError("整理服務炸了")
        ans = type("A", (), {"answer": staticmethod(boom)})()
        out = self._make(answerer=ans).run("MATCH query")
        self.assertIsNotNone(out.overview_error)              # 整理失敗 → 友善訊息
        self.assertEqual(len(out.results), 3)                 # 但結果仍在（可收進）

    def test_empty_results(self):
        out = self._make(results=[]).run("冷門")
        self.assertEqual(out.results, [])
        self.assertFalse(out.no_material)                     # 查無≠無材料；由頁面顯示查無


class _CountingWS:
    """依 query 回不同結果（含跨角度重複 url），並計 search 呼叫次數。"""

    def __init__(self):
        self.calls = 0
        self._by_q = {
            "MATCH query": [SearchResult("原題A", "https://a/1", "s1 MATCH"),
                            SearchResult("原題B", "https://a/2", "s2")],
            "MATCH query 原理": [SearchResult("原理X", "https://a/3", "s3"),
                                 SearchResult("重複", "https://a/1", "dup")],   # a/1 重複
        }

    def search(self, q):
        self.calls += 1
        return self._by_q.get(q, [SearchResult(f"角度-{q}", f"https://ang/{self.calls}", "s")])


class _StubExpander:
    def __init__(self, subs): self._subs = subs
    def expand(self, q): return list(self._subs)


class TestSmartSearchExplore(unittest.TestCase):
    def _make(self, ws, expander, max_subqueries=5):
        return SmartSearch(web_search=ws, embedder=KwEmbedder(),
                           answerer=FixedAnswerer("整理[1]"), fetch=_fetch_ok,
                           expander=expander, max_subqueries=max_subqueries)

    def test_explore_fanout_merges_and_dedups(self):
        ws = _CountingWS()
        out = self._make(ws, _StubExpander(["MATCH query 原理"])).run("MATCH query", explore=True)
        urls = [r.url for r in out.results]
        self.assertEqual(len(urls), len(set(urls)))           # 去重：無重複 url
        self.assertIn("https://a/3", urls)                    # 子角度帶來的新結果
        self.assertEqual(urls.count("https://a/1"), 1)        # 跨角度重複 a/1 只一則
        self.assertGreaterEqual(ws.calls, 2)                  # 原題＋子角度各搜

    def test_explore_caps_subqueries(self):
        ws = _CountingWS()
        subs = [f"角度{i}" for i in range(10)]                 # 給 10 個
        self._make(ws, _StubExpander(subs), max_subqueries=3).run("MATCH query", explore=True)
        self.assertLessEqual(ws.calls, 3)                     # 原題＋子角度合計 ≤ 上限

    def test_explore_false_searches_once(self):
        ws = _CountingWS()
        self._make(ws, _StubExpander(["x"])).run("MATCH query", explore=False)
        self.assertEqual(ws.calls, 1)                         # 不勾＝單搜尋（增量 b）

    def test_expander_failure_falls_back_to_single(self):
        ws = _CountingWS()

        class Boom:
            def expand(self, q): raise RuntimeError("拆解炸了")
        out = self._make(ws, Boom()).run("MATCH query", explore=True)
        self.assertEqual(ws.calls, 1)                         # 退回單 query
        self.assertTrue(out.results)                          # 仍有結果、不拋


if __name__ == "__main__":
    unittest.main()
