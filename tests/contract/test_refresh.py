"""T002-T005 [US1/2/3]：首頁重新整理——重整→存新匯整→首頁顯最新；失敗友善；鈕/成本提示；不自動。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.models import Article, Digest, DigestEntry, Item
from learnnews.sources.base import SourceUnavailable
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db
from tests.web_helpers import build_app


def _digest(date, title):
    return Digest(date=date, entries=[DigestEntry(
        item=Item(source_id="s", external_id="", title=title, url="https://a/x"),
        rank=1, relevance_score=0.9, matched_topic="",
        article=Article(item_id=0, body="b", source_url="https://a/x", headline=title))])


class TestRefresh(unittest.TestCase):
    def test_refresh_creates_and_shows_latest(self):
        db = temp_db()
        app = build_app(db)
        app.state.digest_refresh_factory = lambda config, repo: repo.save_digest(
            _digest("2026-07-25", "重整後的新標題"))
        client = TestClient(app)
        r = client.post("/digest/refresh", follow_redirects=False)
        self.assertEqual(r.status_code, 303)                  # 導回首頁
        self.assertEqual(r.headers["location"], "/")
        home = client.get("/")
        self.assertIn("重整後的新標題", home.text)             # 首頁顯最新

    def test_refresh_keeps_old_digest(self):
        db = temp_db()
        Repository(db).save_digest(_digest("2026-07-24", "舊匯整標題"))
        app = build_app(db)
        app.state.digest_refresh_factory = lambda config, repo: repo.save_digest(
            _digest("2026-07-25", "新匯整標題"))
        client = TestClient(app)
        client.post("/digest/refresh")
        self.assertIn("新匯整標題", client.get("/").text)      # 首頁顯新
        # 舊的仍在 DB
        repo = Repository(db)
        dates = [r["date"] for r in repo.conn.execute(
            "SELECT date FROM digests ORDER BY id").fetchall()]
        repo.close()
        self.assertEqual(dates.count("2026-07-24"), 1)         # 舊匯整未刪

    def test_refresh_failure_friendly(self):
        db = temp_db()
        Repository(db).save_digest(_digest("2026-07-24", "既有匯整"))
        app = build_app(db)

        def boom(config, repo):
            raise SourceUnavailable("模擬來源全掛")
        app.state.digest_refresh_factory = boom
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/digest/refresh", follow_redirects=False)
        self.assertEqual(r.status_code, 303)                  # 非 500
        self.assertIn("msg=refresh_fail", r.headers["location"])
        page = client.get("/?msg=refresh_fail")
        self.assertNotIn("Traceback", page.text)
        self.assertIn("既有匯整", page.text)                   # 舊匯整不受影響

    def test_button_and_cost_hint_and_no_auto(self):
        db = temp_db()
        app = build_app(db)
        called = {"n": 0}

        def factory(config, repo):
            called["n"] += 1
        app.state.digest_refresh_factory = factory
        client = TestClient(app)
        home = client.get("/")
        self.assertIn('action="/digest/refresh"', home.text)  # 重整表單
        self.assertIn("重新消化", home.text)                   # 成本提示字樣
        self.assertEqual(called["n"], 0)                       # 只 GET 不觸發（不自動）


if __name__ == "__main__":
    unittest.main()
