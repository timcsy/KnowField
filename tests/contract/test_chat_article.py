"""契約：帶文章進 /chat（spec 041）。離線注入、零外呼。"""
import json
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_MARK = "藍鯨吃拉麵"          # 只在文章裡出現 → 探針


def _seed_article(db):
    repo = Repository(db)
    aid = repo.save_article("擴散", "擴散與流匹配", f"# 標題\n\n{_MARK}\n")
    repo.close()
    return aid


def _sse(resp):
    out = []
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            out.append(json.loads(line[5:].strip()))
    return out


class TestChatArticle(unittest.TestCase):
    def test_missing_article_reports_error(self):
        """憲章 V：找不到就明講，不靜默略過。"""
        db = temp_db()
        c = TestClient(build_app(db))
        r = c.post("/api/chat/stream",
                   json={"history": [], "message": "想到一件事", "article_id": 99999})
        self.assertEqual(r.status_code, 200)
        evs = _sse(r)
        self.assertTrue(any(e.get("type") == "error" for e in evs),
                        f"沒有回報找不到文章：{evs}")

    def test_article_content_reaches_the_model(self):
        """US1／SC-002：帶了文章，送給模型的脈絡要含它的內容。

        ⚠️ 這條會抓到一個真實的坑：`get_article` 回的是 **dict**，
        用 `getattr(a, "markdown", "")` 會**靜默取到空字串**——功能看起來在跑、
        實際什麼都沒帶進去（又是一次「不會變的訊號」）。
        """
        db = temp_db()
        aid = _seed_article(db)
        app = build_app(db)
        seen = {}
        orig = app.state.chat_factory

        from knowfield.chat.field_chat import FieldChat
        real_msgs = FieldChat._messages

        def spy(self, *a, **kw):
            ms = real_msgs(self, *a, **kw)
            seen["blob"] = str(ms)
            return ms
        FieldChat._messages = spy
        try:
            TestClient(app).post("/api/chat/stream",
                                 json={"history": [], "message": "想到一件事",
                                       "article_id": aid})
        finally:
            FieldChat._messages = real_msgs
            app.state.chat_factory = orig
        self.assertIn(_MARK, seen.get("blob", ""), "文章內容沒有進到送給模型的脈絡")

    def test_no_article_id_unchanged(self):
        """SC-004／FR-006：沒帶文章時行為與現況相同。"""
        db = temp_db()
        c = TestClient(build_app(db))
        r = c.post("/api/chat/stream", json={"history": [], "message": "你好"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(any(e.get("type") == "error" for e in _sse(r)))
