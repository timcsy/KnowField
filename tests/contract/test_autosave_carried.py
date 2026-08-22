"""契約：由來透過 autosave 落庫（spec 044）。離線、零外呼。"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_H = [{"role": "user", "content": "第一句"}]


def _row(db, cid):
    repo = Repository(db)
    r = repo.conn.execute(
        "SELECT carried_kind, carried_ref FROM conversations WHERE id=%s", (cid,)).fetchone()
    repo.close()
    return (r["carried_kind"], r["carried_ref"])


class TestAutosaveCarried(unittest.TestCase):
    def test_article_origin_flows_through_route(self):
        db = temp_db(); c = TestClient(build_app(db))
        tid = c.post("/api/chat/autosave", json={
            "history": _H, "temp_id": None,
            "carried_kind": "article", "carried_ref": "7"}).json()["temp_id"]
        self.assertEqual(_row(db, tid), ("article", "7"))

    def test_source_origin_flows_through_route(self):
        db = temp_db(); c = TestClient(build_app(db))
        tid = c.post("/api/chat/autosave", json={
            "history": _H, "temp_id": None,
            "carried_kind": "source", "carried_ref": "https://x/1"}).json()["temp_id"]
        self.assertEqual(_row(db, tid), ("source", "https://x/1"))

    def test_without_carried_is_unchanged(self):
        """⚠️ FR-010：沒帶時請求／回應與現況逐字相同。
        比對寫死的預期形狀（temp_id ＋ title 兩個鍵），不是拿自己比自己。"""
        db = temp_db(); c = TestClient(build_app(db))
        r = c.post("/api/chat/autosave", json={"history": _H, "temp_id": None}).json()
        self.assertEqual(set(r.keys()), {"temp_id", "title"})
        self.assertEqual(_row(db, r["temp_id"]), ("", ""))


class _Cap:
    def __init__(self): self.messages = None
    def reply(self, m): self.messages = m; return "好"
    def stream(self, m): self.messages = m; yield "好"


class TestContextUnchanged(unittest.TestCase):
    """⚠️ FR-007／SC-005：由來是**元資料**，落庫不得改變送給模型的任何一個字。

    041 FR-003 的閘門（冊封候選不得由文章原文生成）靠的就是「帶入物不進 history」。
    這一刀若讓由來漏進脈絡，那道閘門就破了。
    """

    def _ctx(self, db, **body):
        app = build_app(db)
        cap = _Cap(); app.state.chat_backend_for_test = cap
        app.state.corpus_search_for_test = lambda q: []
        TestClient(app).post("/api/chat/stream",
                             json={"history": [], "message": "嗨", **body})
        return [dict(m) for m in cap.messages]

    def test_context_is_byte_identical_with_or_without_provenance(self):
        db = temp_db()
        c = TestClient(build_app(db))
        c.post("/api/chat/autosave", json={"history": _H, "temp_id": None,
                                           "carried_kind": "article", "carried_ref": "7"})
        after = self._ctx(db)
        before = self._ctx(temp_db())          # 對照組：從沒寫過由來的庫
        self.assertEqual(after, before, "由來落庫改變了送給模型的脈絡")

    def test_provenance_string_never_appears_in_context(self):
        """更直接的一條：那兩個欄位的值不得出現在任何訊息裡。"""
        db = temp_db()
        TestClient(build_app(db)).post("/api/chat/autosave", json={
            "history": _H, "temp_id": None,
            "carried_kind": "source", "carried_ref": "https://zzz-provenance-marker/1"})
        joined = "\n".join(m["content"] for m in self._ctx(db))
        self.assertNotIn("zzz-provenance-marker", joined)
        self.assertNotIn("carried_kind", joined)
