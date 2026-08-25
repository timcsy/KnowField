"""spec 051：出生就歸位——新東西生在你站的地方。

⚠️ **繼承 ≠ 自動分類**：不看內容、只看出處。它錯的時候是「你把出處放錯了」，
不是「模型猜錯了」——那是這一刀跟已被否決四次的自動分類唯一但決定性的差別。

兩條會沉默出錯的規則，各自釘死：
① 多個出處分屬不同領域 → **最近共同祖先**（導出，不是猜）。
② 出處在**根領域** → **沒有訊號**，不是「答案是根」。不然一條沒歸位的出處就把答案全拉回根。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db


class TestInheritDomain(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())
        self.ai = self.repo.create_domain("AI")
        self.gen = self.repo.create_domain("生成模型", self.ai)
        self.math = self.repo.create_domain("數學", self.ai)
        self.flow = self.repo.create_domain("Flow Matching", self.gen)
        self.bio = self.repo.create_domain("生物")          # 另一棵樹

    def tearDown(self):
        self.repo.close()

    # ── FR-004：最近共同祖先 ─────────────────────────────────────

    def test_single_parent_gives_its_own_domain(self):
        self.assertEqual(self.repo.lca_domain([self.gen]), self.gen)

    def test_siblings_give_their_parent(self):
        """AI/生成模型 ＋ AI/數學 → AI。這是**導出**，不是猜。"""
        self.assertEqual(self.repo.lca_domain([self.gen, self.math]), self.ai)

    def test_ancestor_and_descendant_give_the_ancestor(self):
        """AI ＋ AI/生成模型/Flow Matching → AI（祖先本身就是共同祖先）。"""
        self.assertEqual(self.repo.lca_domain([self.ai, self.flow]), self.ai)

    def test_unrelated_trees_give_root(self):
        """兩棵不相干的樹只共有根 → None（根領域）。"""
        self.assertIsNone(self.repo.lca_domain([self.flow, self.bio]))

    def test_three_parents(self):
        self.assertEqual(self.repo.lca_domain([self.flow, self.math, self.gen]), self.ai)

    # ── FR-005：根領域的出處＝沒有訊號 ───────────────────────────

    def test_a_root_parent_is_not_a_vote(self):
        """⚠️ 一條還在根領域的出處 MUST NOT 把答案拉回根。

        它說的是「我還沒被放過」，不是「答案是根」——同 spec 050 FR-007 的區分。
        """
        self.assertEqual(self.repo.lca_domain([self.gen, None]), self.gen)

    def test_all_parents_at_root_gives_no_signal(self):
        self.assertIsNone(self.repo.lca_domain([None, None]))

    def test_no_parents_gives_no_signal(self):
        self.assertIsNone(self.repo.lca_domain([]))

    # ── FR-006：沒訊號時退回當前領域 ─────────────────────────────

    def test_falls_back_to_current_domain(self):
        self.assertEqual(self.repo.inherited_domain([], current=self.math), self.math)

    def test_provenance_beats_current_domain(self):
        """⚠️ 出處**勝過**你站的地方——出處是事實，站的地方只是預設。"""
        self.assertEqual(self.repo.inherited_domain([self.gen], current=self.math), self.gen)

    def test_root_parents_fall_back_to_current(self):
        self.assertEqual(self.repo.inherited_domain([None], current=self.math), self.math)

    def test_no_signal_and_no_current_gives_root(self):
        self.assertIsNone(self.repo.inherited_domain([], current=None))

    # ── 護欄：不看內容 ───────────────────────────────────────────

    def test_lca_is_cycle_safe(self):
        """領域樹理論上不該有環（move_domain 會擋），但 LCA MUST NOT 因此掛掉。"""
        self.repo.conn.execute("UPDATE domains SET parent_id=%s WHERE id=%s", (self.flow, self.ai))
        self.repo.conn.commit()
        self.repo.lca_domain([self.flow, self.math])        # 不能無限迴圈


if __name__ == "__main__":
    unittest.main()


class TestPlaceNew(unittest.TestCase):
    """整合層：出處就是 `_neighbours`，所以一個方法服務三條出生路徑。"""

    def setUp(self):
        self.repo = Repository(temp_db())
        self.ai = self.repo.create_domain("AI")
        self.gen = self.repo.create_domain("生成模型", self.ai)
        self.math = self.repo.create_domain("數學", self.ai)

    def tearDown(self):
        self.repo.close()

    def _conv(self, domain=None):
        return self.repo.autosave_temporary(
            None, [{"role": "user", "content": "嗨"}], "2026-08-26T00:00:00Z", domain_id=domain)

    def _root(self, claim, cid=None, domain=None):
        r = self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, conversation_id, domain_id)"
            " VALUES (%s,'推論','anointed',%s,%s) RETURNING id", (claim, cid, domain)).fetchone()
        self.repo.conn.commit()
        return int(r["id"])

    def test_root_inherits_its_conversation(self):
        c = self._conv(self.gen)
        w = self._root("理解", c)
        self.assertEqual(self.repo.place_new("why_node", w, current=None), self.gen)

    def test_article_from_two_domains_lands_on_their_ancestor(self):
        w1 = self._root("理解1", None, self.gen)
        w2 = self._root("理解2", None, self.math)
        aid = self.repo.save_article("t", "標題", "內文", root_ids=[w1, w2])
        self.assertEqual(self.repo.place_new("article", aid, current=None), self.ai)

    def test_a_root_domain_parent_does_not_drag_the_answer_to_root(self):
        """⚠️ 一條還在根領域的出處不算一票——否則 backlog 清空前這一刀幾乎不生效。"""
        w1 = self._root("已歸位", None, self.gen)
        w2 = self._root("還在根", None, None)
        aid = self.repo.save_article("t", "標題", "內文", root_ids=[w1, w2])
        self.assertEqual(self.repo.place_new("article", aid, current=None), self.gen)

    def test_no_provenance_uses_where_you_stand(self):
        c = self._conv(None)
        w = self._root("理解", c)
        self.assertEqual(self.repo.place_new("why_node", w, current=self.math), self.math)

    def test_calling_before_the_link_exists_loses_the_domain(self):
        """⚠️ 呼叫時機的護欄：連結還沒建好就呼叫，東西會安靜地落在根。

        這條測試在**釘住順序**——`_do_anoint` 是先冊封、後連對話的。
        """
        w = self._root("還沒連上對話", None, None)      # 尚無鄰居
        self.assertIsNone(self.repo.place_new("why_node", w, current=None))
        c = self._conv(self.gen)                        # 之後才連上
        self.repo.conn.execute("UPDATE why_nodes SET conversation_id=%s WHERE id=%s", (c, w))
        self.repo.conn.commit()
        self.assertEqual(self.repo.place_new("why_node", w, current=None), self.gen)
