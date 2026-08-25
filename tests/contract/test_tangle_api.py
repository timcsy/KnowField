"""契約：糾纏預覽與搬動（spec 049；spec 050 起走批次端點）。"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_M = [{"role": "user", "content": "嗨"}]


def _seed(db):
    repo = Repository(db)
    a = repo.create_domain("A"); b = repo.create_domain("B")
    c = repo.autosave_temporary(None, _M, "2026-08-25T00:00:00Z", domain_id=a)
    r = repo.conn.execute(
        "INSERT INTO why_nodes (claim, kind, status, conversation_id, domain_id)"
        " VALUES ('某條理解','推論','anointed',%s,%s) RETURNING id", (c, a)).fetchone()
    w = int(r["id"]); repo.conn.commit(); repo.close()
    return a, b, c, w


class TestTangleApi(unittest.TestCase):
    def test_preview_lists_tangles_with_labels(self):
        db = temp_db(); a, b, c, w = _seed(db)
        r = TestClient(build_app(db)).post(
            "/api/knowledge/tangles",
            json={"items": [{"kind": "conversation", "ref": c}], "domain_id": b}).json()
        self.assertEqual([t["ref"] for t in r["tangles"]], [w])
        self.assertIn("某條理解", r["tangles"][0]["label"])

    def test_preview_changes_nothing(self):
        """⚠️ 預覽就是預覽——不能有副作用。"""
        db = temp_db(); a, b, c, w = _seed(db)
        cl = TestClient(build_app(db))
        cl.post("/api/knowledge/tangles",
            json={"items": [{"kind": "conversation", "ref": c}], "domain_id": b})
        repo = Repository(db)
        self.assertEqual(repo.get_conversation(c).domain_id, a)
        self.assertEqual(repo.knowledge_domain("why_node", w), a)
        repo.close()

    def test_move_without_bring_along_leaves_tangle(self):
        db = temp_db(); a, b, c, w = _seed(db)
        r = TestClient(build_app(db)).post(
            "/api/knowledge/move",
            json={"items": [{"kind": "conversation", "ref": c}], "domain_id": b}).json()
        self.assertEqual(r["tangles"], 1)
        repo = Repository(db)
        self.assertEqual(repo.get_conversation(c).domain_id, b)
        self.assertEqual(repo.knowledge_domain("why_node", w), a)
        repo.close()

    def test_move_with_bring_along(self):
        db = temp_db(); a, b, c, w = _seed(db)
        TestClient(build_app(db)).post(
            "/api/knowledge/move",
            json={"items": [{"kind": "conversation", "ref": c}],
                  "domain_id": b, "bring_along": True})
        repo = Repository(db)
        self.assertEqual(repo.knowledge_domain("why_node", w), b)
        repo.close()

    def test_unknown_kind_rejected(self):
        db = temp_db(); _seed(db)
        r = TestClient(build_app(db)).post(
            "/api/knowledge/move", json={"items": [{"kind": "banana", "ref": 1}]})
        self.assertEqual(r.status_code, 400)
