"""spec 009 /search 路由契約——階段 9 增量 b（spec 010）後改走 smart_search_factory。

原始 WebSearch 後端仍由 tests/unit/test_websearch.py 驗；此處驗路由：列結果/查無/後端失敗/收進。
"""

import unittest

from unittest import mock

from fastapi.testclient import TestClient

from learnnews.rag.types import Source
from learnnews.search.smart import SmartResult
from learnnews.search.websearch import SearchResult
from learnnews.sources.base import SourceUnavailable
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db
from tests.seed_helpers import http_html
from tests.web_helpers import build_app


class TestWebSearch(unittest.TestCase):
    def test_search_lists_results(self):
        app = build_app(temp_db())
        app.state.smart_search_factory = lambda q, explore=False: SmartResult(
            overview="重點[1]", sources=[Source(1, "Attention 解說", "https://blog/attention")],
            results=[SearchResult("Attention 解說", "https://blog/attention", "為什麼 attention 有效")])
        r = TestClient(app).get("/search", params={"q": "attention"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Attention 解說", r.text)
        self.assertIn("https://blog/attention", r.text)      # 可點原文
        self.assertIn('action="/ingest"', r.text)             # 每則有「收進」→ ingest

    def test_search_empty(self):
        app = build_app(temp_db())
        app.state.smart_search_factory = lambda q, explore=False: SmartResult(results=[])
        r = TestClient(app).get("/search", params={"q": "冷門"})
        self.assertIn("查無", r.text)

    def test_search_backend_failure_friendly(self):
        app = build_app(temp_db())

        def boom(q, explore=False):
            raise SourceUnavailable("模擬未設金鑰")

        app.state.smart_search_factory = boom
        r = TestClient(app, raise_server_exceptions=False).get(
            "/search", params={"q": "x"})
        self.assertEqual(r.status_code, 200)                  # 頁內攔，非 500
        self.assertIn("搜尋失敗", r.text)
        self.assertNotIn("Traceback", r.text)

    def test_result_ingest_becomes_seed(self):
        # 收進一則結果的 url → 走既有 /ingest（真實離線）→ 成種子；未收進的不落庫
        db = temp_db()
        app = build_app(db)
        app.state.smart_search_factory = lambda q, explore=False: SmartResult(results=[
            SearchResult("R1", "https://a/keep", "s1"),
            SearchResult("R2", "https://a/skip", "s2")])
        client = TestClient(app)
        client.get("/search", params={"q": "x"})              # 搜尋結果不落庫
        get = http_html("Kept", "attention transformer explained clearly enough here")
        with mock.patch("learnnews.seed.fetch.default_http_get", get):
            client.post("/ingest", data={"ref": "https://a/keep"})   # 只收進一則
        repo = Repository(db)
        urls = {s.url for s in repo.list_seeds()}
        repo.close()
        self.assertIn("https://a/keep", urls)                 # 收進的成種子
        self.assertNotIn("https://a/skip", urls)              # 未收進的不落庫


if __name__ == "__main__":
    unittest.main()
