"""spec 048：領域樹 ＋ 主題路徑。

⚠️ 兩條「不會報錯」型的斷言：
① 路徑由 parent_id **導出**——存字串的話改名／搬家要全量重算，漏算不報錯。
② 搬成環——路徑計算不會爆炸，只會變成無意義的結果。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db


class TestDomainTree(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())

    def tearDown(self):
        self.repo.close()

    def test_create_and_nest(self):
        a = self.repo.create_domain("AI")
        b = self.repo.create_domain("生成模型", a)
        self.assertEqual([d["id"] for d in self.repo.list_domains() if d["parent_id"] == a], [b])

    def test_topic_path(self):
        """SC-001：三層樹的主題路徑 ＝ [A, B, C]。"""
        a = self.repo.create_domain("A")
        b = self.repo.create_domain("B", a)
        c = self.repo.create_domain("C", b)
        self.assertEqual([d["name"] for d in self.repo.domain_path(c)], ["A", "B", "C"])
        self.assertEqual([d["name"] for d in self.repo.domain_path(a)], ["A"])

    def test_same_name_different_parents_differ(self):
        """⚠️ SC-002：領域是**節點**、主題是**路徑**。同名掛不同父＝不同主題。"""
        ai = self.repo.create_domain("AI")
        math = self.repo.create_domain("數學")
        x1 = self.repo.create_domain("生成模型", ai)
        x2 = self.repo.create_domain("生成模型", math)
        p1 = [d["name"] for d in self.repo.domain_path(x1)]
        p2 = [d["name"] for d in self.repo.domain_path(x2)]
        self.assertNotEqual(p1, p2)
        self.assertEqual((p1, p2), (["AI", "生成模型"], ["數學", "生成模型"]))

    def test_rename_changes_path_without_recompute(self):
        """⚠️ FR-003：路徑是導出的——改名後**不必**做任何重算就對了。

        ⚠️ 必須**先讀一次再改名再讀**：只在改名後讀的話，任何快取／儲存版都還沒被填，
        測試會通過而看起來有牙齒。第一版就是這樣寫的，拿「存路徑」去撞撞不紅。
        """
        a = self.repo.create_domain("A")
        c = self.repo.create_domain("C", a)
        before = [d["name"] for d in self.repo.domain_path(c)]   # ← 先讀（會填滿任何快取）
        self.assertEqual(before, ["A", "C"])
        self.repo.rename_domain(a, "AI")
        self.assertEqual([d["name"] for d in self.repo.domain_path(c)], ["AI", "C"])

    def test_move_reflects_in_path_immediately(self):
        """同上，針對**搬家**：先讀、搬、再讀。"""
        a = self.repo.create_domain("A")
        b = self.repo.create_domain("B")
        c = self.repo.create_domain("C", a)
        self.assertEqual([d["name"] for d in self.repo.domain_path(c)], ["A", "C"])
        self.repo.move_domain(c, b)
        self.assertEqual([d["name"] for d in self.repo.domain_path(c)], ["B", "C"])

    def test_move_rejects_cycle(self):
        """⚠️ SC-003：把 A 搬到自己的子孫 C 底下 → 被拒，且樹維持原狀。
        不擋的話路徑計算不會報錯，只會變成無意義的結果。"""
        a = self.repo.create_domain("A")
        b = self.repo.create_domain("B", a)
        c = self.repo.create_domain("C", b)
        with self.assertRaises(ValueError):
            self.repo.move_domain(a, c)
        self.assertEqual([d["name"] for d in self.repo.domain_path(c)], ["A", "B", "C"])

    def test_move_to_self_rejected(self):
        a = self.repo.create_domain("A")
        with self.assertRaises(ValueError):
            self.repo.move_domain(a, a)

    def test_move_ok(self):
        a = self.repo.create_domain("A")
        b = self.repo.create_domain("B")
        c = self.repo.create_domain("C", a)
        self.repo.move_domain(c, b)
        self.assertEqual([d["name"] for d in self.repo.domain_path(c)], ["B", "C"])

    def test_move_to_root(self):
        a = self.repo.create_domain("A")
        c = self.repo.create_domain("C", a)
        self.repo.move_domain(c, None)
        self.assertEqual([d["name"] for d in self.repo.domain_path(c)], ["C"])


class TestConversationDomain(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())

    def tearDown(self):
        self.repo.close()

    def test_unassigned_by_default(self):
        """⚠️ FR-006：未歸屬＝沒有值，不是一個 magic root 節點。"""
        cid = self.repo.autosave_temporary(None, [{"role": "user", "content": "嗨"}],
                                           "2026-08-25T00:00:00Z")
        self.assertIsNone(self.repo.get_conversation(cid).domain_id)

    def test_assign(self):
        d = self.repo.create_domain("AI")
        cid = self.repo.autosave_temporary(None, [{"role": "user", "content": "嗨"}],
                                           "2026-08-25T00:00:00Z", domain_id=d)
        self.assertEqual(self.repo.get_conversation(cid).domain_id, d)

    def test_set_later(self):
        d = self.repo.create_domain("AI")
        cid = self.repo.autosave_temporary(None, [{"role": "user", "content": "嗨"}],
                                           "2026-08-25T00:00:00Z")
        self.repo.set_conversation_domain(cid, d)
        self.assertEqual(self.repo.get_conversation(cid).domain_id, d)

    def test_domain_is_not_rewritten_by_autosave(self):
        """⚠️ 同 spec 044 的由來：歸屬只在明講時改，後續 autosave 不該覆寫掉。"""
        d = self.repo.create_domain("AI")
        m = [{"role": "user", "content": "嗨"}]
        cid = self.repo.autosave_temporary(None, m, "2026-08-25T00:00:00Z", domain_id=d)
        self.repo.autosave_temporary(cid, m + [{"role": "assistant", "content": "好"}],
                                     "2026-08-25T00:01:00Z")
        self.assertEqual(self.repo.get_conversation(cid).domain_id, d)
