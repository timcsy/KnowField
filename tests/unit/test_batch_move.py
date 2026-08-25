"""spec 050：批次搬動——把 N 次偵測併成一次詢問，而併法有一個會誤報的陷阱。

⚠️ 核心：**批次糾纏的判準是「搬完之後會不會不同域」，不是「現在」。**
把對話 A 和它的理解 B 一起搬，單件判準會說「B 在別的領域，這是糾纏」
——但搬完兩者都在目的地，根本沒被拆散。同批成員必須排除。

兩條護欄不變（只算直接連結、連帶只走一層），批次只是把結果併起來。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db

_M = [{"role": "user", "content": "嗨"}]


class TestBatchMove(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())
        self.a = self.repo.create_domain("A")
        self.b = self.repo.create_domain("B")

    def tearDown(self):
        self.repo.close()

    def _conv(self, domain=None):
        return self.repo.autosave_temporary(None, _M, "2026-08-25T00:00:00Z", domain_id=domain)

    def _root(self, claim, cid=None, domain=None, entry=0):
        r = self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, conversation_id, domain_id, source_entry_id)"
            " VALUES (%s,'推論','anointed',%s,%s,%s) RETURNING id",
            (claim, cid, domain, entry)).fetchone()
        self.repo.conn.commit()
        return int(r["id"])

    # ── FR-003：同批成員之間不算糾纏 ──────────────────────────────

    def test_members_of_the_same_batch_are_not_tangled(self):
        """⚠️ 這一條是批次的全部意義：一起搬的東西沒有被拆散。"""
        c = self._conv(self.a)
        r = self._root("理解", c, self.a)
        items = [("conversation", c), ("why_node", r)]
        self.assertEqual(self.repo.batch_tangles(items, self.b), [])

    def test_single_item_of_the_pair_is_still_tangled(self):
        """只搬對話、不搬理解 → 仍是糾纏（證明上一條不是因為偵測壞了才空）。"""
        c = self._conv(self.a)
        r = self._root("理解", c, self.a)
        t = self.repo.batch_tangles([("conversation", c)], self.b)
        self.assertEqual([(x["kind"], x["ref"]) for x in t], [("why_node", r)])

    # ── FR-004：去重 ────────────────────────────────────────────

    def test_shared_neighbour_appears_once(self):
        """兩篇文章長自**同一條**理解 → 一起搬時那條理解只該出現一次。

        ⚠️ fixture 必須真的讓同一鄰居被**兩個**批次成員各碰到一次，
        否則去重被拿掉測試也不會紅（攻擊是 no-op）。
        """
        r = self._root("共用的理解", None, self.a)
        a1 = self.repo.save_article("t1", "b", "zh", root_ids=[r])
        a2 = self.repo.save_article("t2", "b", "zh", root_ids=[r])
        for aid in (a1, a2):
            self.repo.set_knowledge_domain("article", aid, self.a)
        t = self.repo.batch_tangles([("article", a1), ("article", a2)], self.b)
        refs = [(x["kind"], x["ref"]) for x in t]
        self.assertEqual(refs, [("why_node", r)],
                         f"⚠️ 同一鄰居出現不只一次：{refs}")

    # ── FR-007：未歸屬的鄰居不算糾纏 ─────────────────────────────

    def test_unfiled_neighbour_is_not_a_tangle(self):
        c = self._conv(self.a)
        self._root("還沒有位置的理解", c, None)
        self.assertEqual(self.repo.batch_tangles([("conversation", c)], self.b), [])

    # ── FR-002：真的搬 ──────────────────────────────────────────

    def test_batch_move_moves_every_item(self):
        cs = [self._conv(self.a) for _ in range(3)]
        self.repo.batch_move([("conversation", c) for c in cs], self.b)
        for c in cs:
            self.assertEqual(self.repo.knowledge_domain("conversation", c), self.b)

    def test_batch_move_to_unfiled(self):
        c = self._conv(self.a)
        self.repo.batch_move([("conversation", c)], None)
        self.assertIsNone(self.repo.knowledge_domain("conversation", c))

    # ── FR-006：連帶只走一層 ────────────────────────────────────

    def test_bring_along_does_not_recurse(self):
        """對話 → 理解 → 文章。連帶只把理解搬過去，文章留在原地。"""
        c = self._conv(self.a)
        r = self._root("理解", c, self.a)
        aid = self.repo.save_article("t", "b", "zh", root_ids=[r])
        self.repo.set_knowledge_domain("article", aid, self.a)
        self.repo.batch_move([("conversation", c)], self.b, bring_along=True)
        self.assertEqual(self.repo.knowledge_domain("why_node", r), self.b, "理解該被連帶")
        self.assertEqual(self.repo.knowledge_domain("article", aid), self.a,
                         "⚠️ 文章是第二層，MUST NOT 跟著搬")

    # ── FR-005：只算直接連結 ────────────────────────────────────

    def test_only_direct_links(self):
        """對話 → 理解 → 文章：搬對話時，第二層的文章 MUST NOT 出現在糾纏清單。"""
        c = self._conv(self.a)
        r = self._root("理解", c, self.a)
        aid = self.repo.save_article("t", "b", "zh", root_ids=[r])
        self.repo.set_knowledge_domain("article", aid, self.a)
        refs = [(x["kind"], x["ref"]) for x in self.repo.batch_tangles([("conversation", c)], self.b)]
        self.assertIn(("why_node", r), refs)
        self.assertNotIn(("article", aid), refs, "⚠️ 傳遞閉包：第二層不該出現")

    # ── FR-011：預覽零副作用 ────────────────────────────────────

    def test_preview_has_no_side_effects(self):
        c = self._conv(self.a)
        r = self._root("理解", c, self.a)
        self.repo.batch_tangles([("conversation", c)], self.b)
        self.assertEqual(self.repo.knowledge_domain("conversation", c), self.a)
        self.assertEqual(self.repo.knowledge_domain("why_node", r), self.a)


if __name__ == "__main__":
    unittest.main()
