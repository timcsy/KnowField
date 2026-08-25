"""契約：/api/conversations 帶 yield_count（spec 045）。"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_M = [{"role": "user", "content": "嗨"}]


class TestConversationsYield(unittest.TestCase):
    def test_yield_count_reflects_promote_path(self):
        """⚠️ 走冊封的真實路徑（promote_conversation），舊做法在這裡永遠是 0。"""
        db = temp_db()
        repo = Repository(db)
        cid = repo.autosave_temporary(None, _M, "2026-08-23T00:00:00Z")
        wid = int(repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status) VALUES ('冊封的','推論','anointed')"
            " RETURNING id").fetchone()["id"])
        repo.conn.commit()
        repo.promote_conversation(cid, "標題", wid)
        repo.close()
        rows = TestClient(build_app(db)).get("/api/conversations").json()["conversations"]
        row = next(r for r in rows if r["id"] == cid)
        self.assertEqual(row["yield_count"], 1)
        self.assertIsNone(row["why_node_id"], "舊欄位照舊回傳、照舊是空的（不破壞相容）")

    def test_zero_when_no_roots(self):
        db = temp_db()
        repo = Repository(db)
        cid = repo.autosave_temporary(None, _M, "2026-08-23T00:00:00Z")
        repo.close()
        rows = TestClient(build_app(db)).get("/api/conversations").json()["conversations"]
        self.assertEqual(next(r for r in rows if r["id"] == cid)["yield_count"], 0)

    def test_existing_keys_unchanged(self):
        """⚠️ SC-003：既有欄位逐字不變。比對**寫死的鍵集合**，不是拿自己比自己。"""
        db = temp_db()
        repo = Repository(db)
        repo.autosave_temporary(None, _M, "2026-08-23T00:00:00Z")
        repo.close()
        row = TestClient(build_app(db)).get("/api/conversations").json()["conversations"][0]
        self.assertEqual(set(row.keys()),
                         {"id", "title", "created_at", "why_node_id", "count", "yield_count", "domain_id"})
