"""spec 039：譯文落庫的儲存層——**逐翻譯單位**，不是逐文件。零外呼。

⚠️ 為什麼是逐單位：一份 45 個單位的來源只要 1 個降級，逐文件快取就一個字都不能存（FR-006），
而真跑實測就是 45 取 1 ⇒ 使用者要的「自動保存」多半不會發生。逐單位讓成功的存、失敗的永遠重試。

這一層的錯誤都是**沉默**的：命中判錯只讓使用者多等一次、清理判錯只讓他下次多等，
兩者都不會報錯。所以每條都要先看過紅燈。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db

_K1 = "a" * 64
_K2 = "b" * 64


class TestTranslationUnitCache(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())

    def tearDown(self):
        self.repo.close()

    def test_save_then_get(self):
        self.repo.save_translation_units([(_K1, "譯一"), (_K2, "譯二")], "2026-08-21T00:00:00")
        got = self.repo.get_translation_units([_K1, _K2], "2026-08-21T01:00:00")
        self.assertEqual(got, {_K1: "譯一", _K2: "譯二"})

    def test_partial_hit_returns_only_hits(self):
        """FR-004：內容變了 → 那個單位的 key 就不一樣 → 只有它未命中，其餘照舊。
        逐單位的失效比逐文件細：改一段不會讓整篇重翻。"""
        self.repo.save_translation_units([(_K1, "譯一")], "2026-08-21T00:00:00")
        got = self.repo.get_translation_units([_K1, _K2], "2026-08-21T01:00:00")
        self.assertEqual(got, {_K1: "譯一"})

    def test_empty_keys_is_a_no_op(self):
        self.assertEqual(self.repo.get_translation_units([], "2026-08-21T01:00:00"), {})

    def test_save_twice_keeps_one_row(self):
        self.repo.save_translation_units([(_K1, "第一次")], "2026-08-21T00:00:00")
        self.repo.save_translation_units([(_K1, "第二次")], "2026-08-21T00:00:01")
        self.assertEqual(self.repo.get_translation_units([_K1], "2026-08-21T02:00:00"),
                         {_K1: "第二次"})
        n = self.repo.conn.execute(
            "SELECT COUNT(*) AS c FROM translation_units").fetchone()
        self.assertEqual(int(n["c"]), 1)

    def test_get_renews_last_used_at(self):
        """⚠️ 讀取即續命。分成兩個呼叫的話，路由層漏掉續命那步會讓常用的單位被清掉——而那是沉默的。"""
        self.repo.save_translation_units([(_K1, "譯一")], "2026-01-01T00:00:00")
        self.repo.get_translation_units([_K1], "2026-08-21T00:00:00")
        r = self.repo.conn.execute(
            "SELECT last_used_at FROM translation_units WHERE unit_key=%s", (_K1,)).fetchone()
        self.assertEqual(r["last_used_at"], "2026-08-21T00:00:00")

    def test_purge_removes_only_stale(self):
        """FR-005：清理完全自動、以 last_used_at 為唯一依據。"""
        self.repo.save_translation_units([(_K1, "舊")], "2026-01-01T00:00:00")
        self.repo.save_translation_units([(_K2, "新")], "2026-08-01T00:00:00")
        self.assertEqual(self.repo.purge_stale_translations("2026-06-01T00:00:00"), 1)
        self.assertEqual(self.repo.get_translation_units([_K1, _K2], "2026-08-21T00:00:00"),
                         {_K2: "新"})
