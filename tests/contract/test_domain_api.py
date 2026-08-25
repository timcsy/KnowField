"""契約：領域樹 API（spec 048）。

⚠️ 本檔最重要的是 `TestGroundingUnchanged`：這一刀的價值有一半在「安全」——
使用者要用過真的樹，才決定第三刀（RAG scope 改 DAG 可達）。
**若這一刀偷偷改了 grounding，那個判斷就被污染了。**
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_M = [{"role": "user", "content": "嗨"}]


class _Cap:
    def __init__(self): self.messages = None
    def reply(self, m): self.messages = m; return "好"
    def stream(self, m): self.messages = m; yield "好"


class TestDomainApi(unittest.TestCase):
    def test_create_nest_and_path(self):
        c = TestClient(build_app(temp_db()))
        a = c.post("/api/domains", json={"name": "AI"}).json()["id"]
        b = c.post("/api/domains", json={"name": "生成模型", "parent_id": a}).json()["id"]
        d = c.get("/api/domains").json()
        node = next(x for x in d["domains"] if x["id"] == b)
        self.assertEqual([p["name"] for p in node["path"]], ["AI", "生成模型"])

    def test_move_cycle_rejected(self):
        """⚠️ SC-003：搬到自己的子孫底下要被拒，而且樹不動。"""
        c = TestClient(build_app(temp_db()))
        a = c.post("/api/domains", json={"name": "A"}).json()["id"]
        b = c.post("/api/domains", json={"name": "B", "parent_id": a}).json()["id"]
        r = c.post(f"/api/domains/{a}/move", json={"parent_id": b})
        self.assertFalse(r.json().get("ok"))
        node = next(x for x in c.get("/api/domains").json()["domains"] if x["id"] == b)
        self.assertEqual([p["name"] for p in node["path"]], ["A", "B"])

    def test_conversation_domain_assignment(self):
        db = temp_db(); c = TestClient(build_app(db))
        a = c.post("/api/domains", json={"name": "AI"}).json()["id"]
        tid = c.post("/api/chat/autosave", json={"history": _M, "temp_id": None,
                                                 "domain_id": a}).json()["temp_id"]
        repo = Repository(db)
        self.assertEqual(repo.get_conversation(tid).domain_id, a)
        repo.close()

    def test_unassigned_is_null_not_a_node(self):
        """⚠️ FR-006：未歸屬＝沒有值，不是樹上的一個節點。"""
        db = temp_db(); c = TestClient(build_app(db))
        tid = c.post("/api/chat/autosave", json={"history": _M, "temp_id": None}).json()["temp_id"]
        repo = Repository(db)
        self.assertIsNone(repo.get_conversation(tid).domain_id)
        repo.close()
        self.assertEqual(c.get("/api/domains").json()["domains"], [])


class TestGroundingUnchanged(unittest.TestCase):
    """⚠️ FR-009／SC-006：這一刀 MUST NOT 動到 grounding。"""

    def _ctx(self, db):
        app = build_app(db)
        cap = _Cap(); app.state.chat_backend_for_test = cap
        app.state.corpus_search_for_test = lambda q: []
        TestClient(app).post("/api/chat/stream", json={"history": [], "message": "嗨"})
        return [dict(m) for m in cap.messages]

    def test_context_identical_with_and_without_domains(self):
        """建了一整棵樹、把對話歸進去之後，送給模型的脈絡仍**逐字相同**。"""
        db = temp_db(); c = TestClient(build_app(db))
        repo = Repository(db)
        repo.conn.execute("INSERT INTO why_nodes (claim, kind, status)"
                          " VALUES ('某條理解','推論','anointed')")
        repo.conn.commit(); repo.close()
        before = self._ctx(db)
        a = c.post("/api/domains", json={"name": "AI"}).json()["id"]
        c.post("/api/domains", json={"name": "生成模型", "parent_id": a})
        c.post("/api/chat/autosave", json={"history": _M, "temp_id": None, "domain_id": a})
        self.assertEqual(self._ctx(db), before, "領域樹改變了送給模型的脈絡")

    def test_domain_name_never_leaks_into_context(self):
        db = temp_db(); c = TestClient(build_app(db))
        c.post("/api/domains", json={"name": "zzz-domain-marker"})
        joined = "\n".join(m["content"] for m in self._ctx(db))
        self.assertNotIn("zzz-domain-marker", joined)
        self.assertNotIn("domain_id", joined)
