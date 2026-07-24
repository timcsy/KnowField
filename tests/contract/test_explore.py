"""T009/T010/T011 [US1/US2]：/search 深入探索開關——傳遞 explore、checkbox、離線鏈不崩。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.search.smart import SmartResult
from learnnews.search.websearch import SearchResult
from tests.rag_helpers import temp_db
from tests.web_helpers import build_app


class TestExploreWeb(unittest.TestCase):
    def test_route_passes_explore_flag(self):
        app = build_app(temp_db())
        seen = {}

        def factory(q, explore=False):
            seen["explore"] = explore
            return SmartResult(overview="重點[1]", results=[SearchResult("R", "https://a/1", "s")])

        app.state.smart_search_factory = factory
        client = TestClient(app)
        client.get("/search", params={"q": "x", "explore": "1"})
        self.assertTrue(seen["explore"])                      # 勾選 → explore=True
        client.get("/search", params={"q": "x"})
        self.assertFalse(seen["explore"])                     # 不帶 → explore=False

    def test_page_has_explore_checkbox(self):
        app = build_app(temp_db())
        app.state.smart_search_factory = lambda q, explore=False: SmartResult(
            results=[SearchResult("R", "https://a/1", "s")], overview="重點[1]")
        client = TestClient(app)
        r = client.get("/search", params={"q": "x"})
        self.assertIn('name="explore"', r.text)               # 有開關
        r2 = client.get("/search", params={"q": "x", "explore": "1"})
        self.assertIn("checked", r2.text)                     # 勾選狀態回填

    def test_offline_chain_explore_ok(self):
        # 真實 SmartSearch 鏈（離線 stub 各件＋stub fetch，零網路）下勾探索 → 200、不崩
        from learnnews.models import Item
        from learnnews.rag.answerer import StubAnswerer
        from learnnews.ranking.embeddings import HashingEmbedder
        from learnnews.search.expand import StubQueryExpander
        from learnnews.search.smart import SmartSearch
        from learnnews.search.websearch import StubWebSearch

        def fake_fetch(url):
            return Item(source_id="s", external_id="", title="T", url=url, abstract="內文")

        ss = SmartSearch(StubWebSearch(), HashingEmbedder(), StubAnswerer(),
                         fetch=fake_fetch, expander=StubQueryExpander())
        app = build_app(temp_db())
        app.state.smart_search_factory = lambda q, explore=False: ss.run(q, explore)
        r = TestClient(app, raise_server_exceptions=False).get(
            "/search", params={"q": "agent memory", "explore": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Traceback", r.text)


if __name__ == "__main__":
    unittest.main()
