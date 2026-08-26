"""spec 054：刪領域刪的是**位置**，不是知識。

⚠️ 檔案系統刪資料夾會把裡面的檔案一起帶走。**這裡不能照抄**——
裡面是使用者的知識，那是不可逆的損失，而且刪掉之後沒有任何辦法發現「本來有什麼」。
⇒ 刪一個領域＝內容與直屬子領域**上移到父領域**，一件都不少。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db

_M = [{"role": "user", "content": "嗨"}]


class TestDeleteDomain(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())
        self.ai = self.repo.create_domain("AI")
        self.gen = self.repo.create_domain("生成模型", self.ai)
        self.flow = self.repo.create_domain("Flow Matching", self.gen)

    def tearDown(self):
        self.repo.close()

    def _conv(self, domain):
        return self.repo.autosave_temporary(None, _M, "2026-08-26T00:00:00Z", domain_id=domain)

    def _root(self, domain):
        r = self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, domain_id)"
            " VALUES ('理解','推論','anointed',%s) RETURNING id", (domain,)).fetchone()
        self.repo.conn.commit()
        return int(r["id"])

    # ── FR-004：知識一件都不能少 ─────────────────────────────────

    def test_knowledge_moves_up_not_away(self):
        c = self._conv(self.gen)
        w = self._root(self.gen)
        self.repo.delete_domain(self.gen)
        self.assertEqual(self.repo.knowledge_domain("conversation", c), self.ai)
        self.assertEqual(self.repo.knowledge_domain("why_node", w), self.ai)

    def test_nothing_is_deleted(self):
        """⚠️ 最重要的一條：**總數不變**。"""
        self._conv(self.gen); self._root(self.gen); self._conv(self.flow)
        before = len(self.repo._inventory_rows())
        self.repo.delete_domain(self.gen)
        self.assertEqual(len(self.repo._inventory_rows()), before, "刪領域把知識刪掉了")

    def test_subdomains_move_up_and_survive(self):
        self.repo.delete_domain(self.gen)
        names = {d["name"]: d["parent_id"] for d in self.repo.list_domains()}
        self.assertIn("Flow Matching", names, "子領域被連帶刪掉了")
        self.assertEqual(names["Flow Matching"], self.ai, "子領域沒有上移")

    def test_deleting_a_top_level_domain_sends_contents_to_root(self):
        c = self._conv(self.ai)
        self.repo.delete_domain(self.ai)
        self.assertIsNone(self.repo.knowledge_domain("conversation", c))

    def test_the_domain_itself_is_gone(self):
        self.repo.delete_domain(self.gen)
        self.assertNotIn(self.gen, [d["id"] for d in self.repo.list_domains()])

    def test_grandchildren_keep_their_own_parent(self):
        """⚠️ 只上移**直屬**子領域——孫輩仍掛在它們自己的父親底下，不被拉平。"""
        deep = self.repo.create_domain("OT-CFM", self.flow)
        self.repo.delete_domain(self.gen)
        names = {d["id"]: d["parent_id"] for d in self.repo.list_domains()}
        self.assertEqual(names[deep], self.flow, "孫輩被拉平了")

    # ── FR-005：先說出影響範圍 ───────────────────────────────────

    def test_preview_reports_the_blast_radius(self):
        self._conv(self.gen); self._root(self.gen)
        p = self.repo.delete_domain_preview(self.gen)
        self.assertEqual(p["items"], 2)
        self.assertEqual(p["children"], 1)
        self.assertEqual(p["to"], self.ai)

    def test_preview_has_no_side_effects(self):
        self.repo.delete_domain_preview(self.gen)
        self.assertIn(self.gen, [d["id"] for d in self.repo.list_domains()])

    def test_preview_counts_only_direct_contents_not_the_whole_subtree(self):
        """⚠️ 影響範圍是**這個領域自己的**——子孫底下的東西不會動，別嚇人。"""
        self._conv(self.gen); self._conv(self.flow)
        self.assertEqual(self.repo.delete_domain_preview(self.gen)["items"], 1)


if __name__ == "__main__":
    unittest.main()
