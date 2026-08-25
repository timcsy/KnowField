"""spec 046：conversation_referrers 帶回出處範圍。

⚠️ 既有的鍵（id／claim）不能動——那是刪除保護在用的（`delete_conversation` 的前置）。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db

_M = [{"role": "user", "content": f"第{i}句"} for i in range(1, 11)]


class TestReferrerRanges(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())
        self.cid = self.repo.autosave_temporary(None, _M, "2026-08-25T00:00:00Z")

    def tearDown(self):
        self.repo.close()

    def _root(self, claim, f=0, t=0):
        self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, conversation_id, src_from, src_to)"
            " VALUES (%s,'推論','anointed',%s,%s,%s)", (claim, self.cid, f, t))
        self.repo.conn.commit()

    def test_returns_ranges(self):
        self._root("有範圍的", 3, 7)
        r = self.repo.conversation_referrers(self.cid)[0]
        self.assertEqual((r["src_from"], r["src_to"]), (3, 7))

    def test_no_range_is_zero_not_missing(self):
        """舊資料沒有範圍 → 0/0，⚠️ 不是缺鍵（缺鍵會讓前端拿到 undefined 而靜默算錯）。"""
        self._root("沒範圍的")
        r = self.repo.conversation_referrers(self.cid)[0]
        self.assertEqual((r["src_from"], r["src_to"]), (0, 0))

    def test_existing_keys_unchanged(self):
        """⚠️ 刪除保護讀的是 claim；鍵集合比對寫死的，不是拿自己比自己。"""
        self._root("某條", 1, 2)
        r = self.repo.conversation_referrers(self.cid)[0]
        self.assertEqual(set(r.keys()), {"id", "claim", "src_from", "src_to"})
