"""契約：對話不再分暫存／永久（spec 040）。

⚠️ 這是**移除**功能。風險不對稱——做多了會刪掉使用者的東西。
所以最重的一條測試不是「分層沒了」，是「**資料一筆都不能少**」。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


def _seed(db):
    """種三筆：兩筆原本是暫存、一筆原本是永久。"""
    repo = Repository(db)
    a = repo.autosave_temporary(None, [{"role": "user", "content": "暫存一"}], "2026-08-01T00:00:00")
    b = repo.autosave_temporary(None, [{"role": "user", "content": "暫存二"}], "2026-07-01T00:00:00")
    c = repo.autosave_temporary(None, [{"role": "user", "content": "永久"}], "2026-08-18T00:00:00")
    repo.promote_conversation(c, title="留著的")
    repo.close()
    return {a, b, c}


class TestNoTempTier(unittest.TestCase):
    def test_all_conversations_survive(self):
        """SC-001／FR-005：移除分層不得動到任何一筆資料。

        ⚠️ 其中一筆的 last_activity 是 2026-07-01（舊制下早就過期該被清）。
        它**必須還在**——移除的是機制，不是資料。
        """
        db = temp_db()
        ids = _seed(db)
        c = TestClient(build_app(db))
        r = c.get("/api/conversations").json()
        got = {x["id"] for x in r["conversations"]}
        self.assertEqual(got, ids, "少了或多了對話——移除機制時動到了資料")

    def test_single_group_no_temporary_split(self):
        """FR-002：單一分組，回應裡不再有 permanent/temporary 兩個桶。"""
        db = temp_db()
        _seed(db)
        r = TestClient(build_app(db)).get("/api/conversations").json()
        self.assertIn("conversations", r)
        self.assertNotIn("temporary", r)
        self.assertNotIn("permanent", r)

    def test_conversation_payload_has_no_temporary_flag(self):
        """FR-001：單筆對話不再帶暫存旗標。"""
        db = temp_db()
        ids = _seed(db)
        cid = sorted(ids)[0]
        d = TestClient(build_app(db)).get(f"/api/conversations/{cid}").json()
        self.assertTrue(d["found"])
        self.assertNotIn("temporary", d)

    def test_nothing_is_auto_deleted_by_age(self):
        """FR-004：不得再依時間自動刪除。反覆呼叫清單也不會少。"""
        db = temp_db()
        ids = _seed(db)
        c = TestClient(build_app(db))
        for _ in range(3):
            c.get("/api/conversations")
        repo = Repository(db)
        remaining = {x.id for x in repo.list_conversations()}
        repo.close()
        self.assertEqual(remaining, ids)

    def test_autosave_still_works(self):
        """FR-006：安全網保留——沒按任何存檔動作的對話仍然留得住。"""
        db = temp_db()
        repo = Repository(db)
        before = len(repo.list_conversations())
        cid = repo.autosave_temporary(None, [{"role": "user", "content": "沒按存"}],
                                      "2026-08-18T00:00:00")
        after = repo.list_conversations()
        repo.close()
        self.assertEqual(len(after), before + 1)
        self.assertIn(cid, {c.id for c in after})

    def test_resume_updates_same_row(self):
        """FR-007：接回繼續聊更新同一筆，不另開。"""
        db = temp_db()
        repo = Repository(db)
        cid = repo.autosave_temporary(None, [{"role": "user", "content": "一"}],
                                      "2026-08-18T00:00:00")
        n1 = len(repo.list_conversations())
        repo.autosave_temporary(cid, [{"role": "user", "content": "一"},
                                      {"role": "assistant", "content": "二"}],
                                "2026-08-18T00:01:00")
        convs = repo.list_conversations()
        repo.close()
        self.assertEqual(len(convs), n1, "接回時另開了一筆")
