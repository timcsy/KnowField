"""spec 044：帶入物的由來只在**建立**那一刻寫，之後永不改寫。

⚠️ 「由來」記的是「它從哪來的」——那是歷史事實，不是當前狀態。
所以 UPDATE 分支一個字都不該碰它，而測試要**故意送不同的值**去撞，
不然「不變」這條斷言會被「反正也沒送別的」滿足（斷言被你以為之外的東西滿足）。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db

_M1 = [{"role": "user", "content": "第一句"}]
_M2 = [{"role": "user", "content": "第一句"}, {"role": "assistant", "content": "答"}]


class TestCarriedProvenance(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())

    def tearDown(self):
        self.repo.close()

    def _row(self, cid):
        return self.repo.conn.execute(
            "SELECT carried_kind, carried_ref FROM conversations WHERE id=%s", (cid,)).fetchone()

    def test_article_origin_recorded(self):
        cid = self.repo.autosave_temporary(None, _M1, "2026-08-22T00:00:00Z",
                                           carried_kind="article", carried_ref="12")
        r = self._row(cid)
        self.assertEqual((r["carried_kind"], r["carried_ref"]), ("article", "12"))

    def test_source_origin_recorded(self):
        cid = self.repo.autosave_temporary(None, _M1, "2026-08-22T00:00:00Z",
                                           carried_kind="source", carried_ref="https://x/1")
        r = self._row(cid)
        self.assertEqual((r["carried_kind"], r["carried_ref"]), ("source", "https://x/1"))

    def test_no_carry_is_empty(self):
        cid = self.repo.autosave_temporary(None, _M1, "2026-08-22T00:00:00Z")
        r = self._row(cid)
        self.assertEqual((r["carried_kind"], r["carried_ref"]), ("", ""))

    def test_origin_never_rewritten(self):
        """⚠️ 本檔核心：第二、三次故意送**不同**的由來，仍必須是最初那個。"""
        cid = self.repo.autosave_temporary(None, _M1, "2026-08-22T00:00:00Z",
                                           carried_kind="article", carried_ref="12")
        self.repo.autosave_temporary(cid, _M2, "2026-08-22T00:01:00Z",
                                     carried_kind="source", carried_ref="https://evil/9")
        self.repo.autosave_temporary(cid, _M2, "2026-08-22T00:02:00Z")
        r = self._row(cid)
        self.assertEqual((r["carried_kind"], r["carried_ref"]), ("article", "12"))

    def test_update_still_updates_messages(self):
        """前提：上一條要有意義，UPDATE 本身得真的有在更新（否則它測的是「什麼都沒發生」）。"""
        cid = self.repo.autosave_temporary(None, _M1, "2026-08-22T00:00:00Z")
        self.repo.autosave_temporary(cid, _M2, "2026-08-22T00:01:00Z")
        self.assertEqual(len(self.repo.get_conversation(cid).messages), 2)
