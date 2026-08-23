"""spec 045：一段對話「聊出了幾條核心理解」——讀事實來源，不讀那個只填一半的舊欄位。

⚠️ 缺陷本體在 ③：冊封走的是 `promote_conversation`，它**只更新 why_nodes 側**，
所以舊做法（讀 `conversations.why_node_id`）在真實路徑上永遠是 0。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db

_M = [{"role": "user", "content": "嗨"}]


class _CountingConn:
    """數 execute 次數——效能斷言用。⚠️ 純看輸出分不出逐筆與批次。"""

    def __init__(self, inner):
        self._inner, self.n = inner, 0
        self.dialect = inner.dialect

    def execute(self, sql, params=None):
        self.n += 1
        return self._inner.execute(sql, params)

    def commit(self): self._inner.commit()
    def close(self): self._inner.close()


class TestConversationYield(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())

    def tearDown(self):
        self.repo.close()

    def _conv(self, title="對話"):
        return self.repo.autosave_temporary(None, _M, "2026-08-23T00:00:00Z")

    def _root(self, claim, cid=None):
        r = self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, conversation_id)"
            " VALUES (%s,'推論','anointed',%s) RETURNING id", (claim, cid)).fetchone()
        self.repo.conn.commit()
        return int(r["id"])

    def test_counts_roots_pointing_at_it(self):
        cid = self._conv()
        self._root("第一條", cid); self._root("第二條", cid)
        self.assertEqual(self.repo.conversation_yield_counts().get(cid), 2)

    def test_zero_when_nothing_points_at_it(self):
        cid = self._conv()
        self._root("與這段無關", None)
        self.assertEqual(self.repo.conversation_yield_counts().get(cid, 0), 0)

    def test_promote_path_is_counted(self):
        """⚠️ 缺陷本體：冊封走 promote_conversation，它只更新 why_nodes 側。
        舊做法（讀 conversations.why_node_id）在這條路上永遠是 0。"""
        cid = self._conv()
        wid = self._root("冊封出來的", None)
        self.repo.promote_conversation(cid, "落點標題", wid)
        self.assertEqual(self.repo.conversation_yield_counts().get(cid), 1)
        # 對照：那個舊欄位在這條路上仍是空的——這正是畫面漏掉 2/3 的原因
        r = self.repo.conn.execute(
            "SELECT why_node_id FROM conversations WHERE id=%s", (cid,)).fetchone()
        self.assertIsNone(r["why_node_id"], "前提：舊欄位在冊封路徑上本來就沒被填")

    def test_query_count_does_not_grow_with_conversations(self):
        """⚠️ FR-003／SC-002：一次 GROUP BY，不是逐筆。效能斷言，綠燈看不出來。"""
        for i in range(6):
            cid = self._conv(f"對話{i}")
            self._root(f"根因{i}", cid)
        self.repo.conn = _CountingConn(self.repo.conn)
        self.repo.conversation_yield_counts()
        self.assertLessEqual(self.repo.conn.n, 2,
                             f"對 6 段對話查了 {self.repo.conn.n} 次——逐筆了")
