"""契約：對話詳情帶回冊封覆蓋（spec 046）。"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_M = [{"role": "user", "content": f"第{i}句"} for i in range(1, 11)]


def _seed(db, ranges):
    repo = Repository(db)
    cid = repo.autosave_temporary(None, _M, "2026-08-25T00:00:00Z")
    for i, (f, t) in enumerate(ranges):
        repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, conversation_id, src_from, src_to)"
            " VALUES (%s,'推論','anointed',%s,%s,%s)", (f"第{i}條", cid, f, t))
    repo.conn.commit(); repo.close()
    return cid


class TestConversationAnointed(unittest.TestCase):
    def test_returns_ranges(self):
        db = temp_db(); cid = _seed(db, [(1, 3), (6, 8)])
        d = TestClient(build_app(db)).get(f"/api/conversations/{cid}").json()
        self.assertEqual([(a["from"], a["to"]) for a in d["anointed"]], [(1, 3), (6, 8)])

    def test_existing_keys_unchanged(self):
        """⚠️ SC-005：既有欄位逐字不變。比對寫死的鍵集合。"""
        db = temp_db(); cid = _seed(db, [(1, 3)])
        d = TestClient(build_app(db)).get(f"/api/conversations/{cid}").json()
        self.assertEqual(set(d.keys()),
                         {"found", "id", "title", "messages", "referrers", "anointed"})
        self.assertEqual(d["referrers"], ["第0條"], "referrers 仍是主張字串陣列（擋編輯用）")

    def test_no_anointment(self):
        db = temp_db(); cid = _seed(db, [])
        d = TestClient(build_app(db)).get(f"/api/conversations/{cid}").json()
        self.assertEqual(d["anointed"], [])


class TestReanoint(unittest.TestCase):
    """spec 046 FR-006/007：重新冊封＝**新增一條**（使用者裁決 2026-08-25）。

    ⚠️ 這兩條現在**本來就成立**（靠既有的 norm_claim 去重）。釘住它們是為了擋
    日後有人「順手」把冊封改成 upsert——那會讓「我當初為什麼信這個」的中間那一步消失。
    """

    def _anoint(self, c, claim, cid=None):
        return c.post("/api/chat/anoint", json={
            "claim": claim, "kind": "推論", "ladder": "", "evidence_urls": "",
            "save_convo": False, "history": _M, "temp_id": cid,
            "src_from": 1, "src_to": 3}).json()

    def _n(self, db):
        repo = Repository(db)
        n = repo.conn.execute("SELECT count(*) AS c FROM why_nodes").fetchone()["c"]
        repo.close()
        return int(n)

    def test_edited_text_adds_one(self):
        db = temp_db(); c = TestClient(build_app(db))
        self._anoint(c, "原本的說法")
        before = self._n(db)
        r = self._anoint(c, "改過之後的說法")
        self.assertEqual(r["status"], "created")
        self.assertEqual(self._n(db), before + 1, "改過文字應該新增一條，不是取代")

    def test_same_text_does_not_add(self):
        db = temp_db(); c = TestClient(build_app(db))
        self._anoint(c, "一樣的說法")
        before = self._n(db)
        r = self._anoint(c, "一樣的說法")
        self.assertEqual(r["status"], "exists")
        self.assertEqual(self._n(db), before, "相同文字不該新增（既有去重）")

    def test_original_is_untouched(self):
        """⚠️ 新增一條 ≠ 動到舊那條。就地改會讓溯源的中間一步消失。"""
        db = temp_db(); c = TestClient(build_app(db))
        self._anoint(c, "原本的說法")
        repo = Repository(db)
        old = repo.conn.execute("SELECT id, claim FROM why_nodes ORDER BY id").fetchone()
        repo.close()
        self._anoint(c, "改過之後的說法")
        repo = Repository(db)
        still = repo.conn.execute("SELECT claim FROM why_nodes WHERE id=%s", (old["id"],)).fetchone()
        repo.close()
        self.assertEqual(still["claim"], old["claim"])
