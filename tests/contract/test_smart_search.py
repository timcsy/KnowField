"""T007/T008/T009 [US3/US4]：/search 顯示整理＋排序＋[n]；降級仍列結果；收進不變。"""

import unittest

from unittest import mock

from fastapi.testclient import TestClient

from learnnews.rag.types import Source
from learnnews.search.smart import SmartResult
from learnnews.search.websearch import SearchResult
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db
from tests.seed_helpers import http_html
from tests.web_helpers import build_app


def _sr():
    return [SearchResult("結果一", "https://a/1", "s1"),
            SearchResult("結果二", "https://a/2", "s2")]


class TestSmartSearchWeb(unittest.TestCase):
    def test_shows_overview_and_ranked_results(self):
        app = build_app(temp_db())
        app.state.smart_search_factory = lambda q: SmartResult(
            overview="重點整理[1][2]",
            sources=[Source(1, "結果一", "https://a/1"), Source(2, "結果二", "https://a/2")],
            results=_sr())
        r = TestClient(app).get("/search", params={"q": "x"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("重點整理", r.text)              # 頂端整理段
        self.assertIn('id="res-1"', r.text)            # 結果卡有錨點
        self.assertIn("#res-", r.text)                 # [n]→#res-n 的渲染 JS
        self.assertIn('action="/ingest"', r.text)      # 每則仍可收進

    def test_no_material_hides_sources(self):
        app = build_app(temp_db())
        app.state.smart_search_factory = lambda q: SmartResult(
            overview="沒有相關材料。", no_material=True, results=_sr())
        r = TestClient(app).get("/search", params={"q": "冷門"})
        self.assertIn("沒有相關材料", r.text)
        self.assertNotIn('href="#res-1"', r.text)      # 無材料就不列 [n] 來源連結

    def test_overview_error_still_lists_results(self):
        app = build_app(temp_db())
        app.state.smart_search_factory = lambda q: SmartResult(
            results=_sr(), overview_error="整理暫時無法產生，以下為原始搜尋結果（仍可收進）。")
        r = TestClient(app).get("/search", params={"q": "x"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("整理暫時無法產生", r.text)       # 友善整理錯誤
        self.assertIn("結果一", r.text)                # 但結果照列
        self.assertIn('action="/ingest"', r.text)      # 仍可收進

    def test_factory_crash_is_friendly_not_500(self):
        app = build_app(temp_db())

        def boom(q):
            raise RuntimeError("整理服務整個炸了")

        app.state.smart_search_factory = boom
        r = TestClient(app, raise_server_exceptions=False).get("/search", params={"q": "x"})
        self.assertEqual(r.status_code, 200)           # 頁內攔、非 500
        self.assertNotIn("Traceback", r.text)
        self.assertIn("搜尋", r.text)                  # 頁面仍在

    def test_result_ingest_becomes_seed(self):
        # US3：收進一則結果 url → 走既有 /ingest（真實離線）→ 成種子
        db = temp_db()
        app = build_app(db)
        app.state.smart_search_factory = lambda q: SmartResult(
            results=[SearchResult("R1", "https://a/keep", "s1")],
            overview="重點[1]", sources=[Source(1, "R1", "https://a/keep")])
        client = TestClient(app)
        client.get("/search", params={"q": "x"})       # 搜尋/整理不落庫
        get = http_html("Kept", "attention transformer explained clearly enough here")
        with mock.patch("learnnews.seed.fetch.default_http_get", get):
            client.post("/ingest", data={"ref": "https://a/keep"})
        repo = Repository(db)
        urls = {s.url for s in repo.list_seeds()}
        repo.close()
        self.assertIn("https://a/keep", urls)


if __name__ == "__main__":
    unittest.main()
