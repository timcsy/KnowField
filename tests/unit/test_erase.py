"""spec 056：第二次的死——抹除，只留一塊疤。

使用者：「我覺得還是可以有刪除，就是**第二次的死**，就是直接抹除，救不回來的」。

不可逆性的層級：冊封（出生）→ 封存（第一次的死，遺骸還在）→ **抹除（第二次的死）**。

⚠️ **抹除只作用在遺骸上**——活的東西**沒有任何單一動作**能一次消失。
這不是多一道確認視窗（那是劇場），是**路徑上真的沒有捷徑**。

⚠️ 留疤的理由：第二次的死該讓**內容**不見；但連「這裡曾經有東西」都不見的話，
那不是死亡，是**從沒存在過**——超新星炸完留下的不是虛空，是一片殘骸雲。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db

_M = [{"role": "user", "content": "嗨"}]
_T1 = "2026-08-26T10:00:00Z"
_T2 = "2026-08-26T11:00:00Z"


class _Base(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())
        self.ai = self.repo.create_domain("AI")
        self.gen = self.repo.create_domain("生成模型", self.ai)

    def tearDown(self):
        self.repo.close()

    def _root(self, claim="一條理解", cid=None):
        r = self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, conversation_id)"
            " VALUES (%s,'推論','anointed',%s) RETURNING id", (claim, cid)).fetchone()
        self.repo.conn.commit()
        return int(r["id"])

    def _conv(self):
        return self.repo.autosave_temporary(None, _M, _T1)


class TestEraseGuards(_Base):
    """FR-001／003：路徑上沒有捷徑。"""

    def test_cannot_erase_something_still_alive(self):
        """⚠️ 這是整個模型的骨架：活的東西不能一步消失。"""
        w = self._root()
        with self.assertRaises(ValueError):
            self.repo.erase_knowledge("why_node", w, _T2)
        self.assertIn(w, [x.id for x in self.repo.list_why_nodes()])

    def test_can_erase_after_archiving(self):
        w = self._root()
        self.repo.archive_knowledge("why_node", w, _T1)
        self.repo.erase_knowledge("why_node", w, _T2)
        self.assertEqual(self.repo.scar("why_node", w)["erased_at"], _T2)

    def test_erased_cannot_be_restored(self):
        w = self._root()
        self.repo.archive_knowledge("why_node", w, _T1)
        self.repo.erase_knowledge("why_node", w, _T2)
        with self.assertRaises(ValueError):
            self.repo.restore_knowledge("why_node", w)


class TestScar(_Base):
    """FR-002：內容全空，列還在。"""

    def test_content_is_gone(self):
        w = self._root("這條會被抹除的內容")
        self.repo.archive_knowledge("why_node", w, _T1)
        self.repo.erase_knowledge("why_node", w, _T2)
        r = self.repo.conn.execute(
            "SELECT claim, evidence_urls, ladder FROM why_nodes WHERE id=%s", (w,)).fetchone()
        self.assertEqual(r["claim"], "")
        self.assertNotIn("這條會被抹除的內容", str(dict(r)))

    def test_the_row_survives_so_the_question_can_be_asked(self):
        """⚠️ 疤要答得出「為什麼這裡是空的」。"""
        w = self._root()
        self.repo.archive_knowledge("why_node", w, _T1)
        self.repo.erase_knowledge("why_node", w, _T2)
        sc = self.repo.scar("why_node", w)
        self.assertEqual((sc["ref"], sc["erased_at"]), (w, _T2))

    def test_a_live_thing_has_no_scar(self):
        w = self._root()
        self.assertIsNone(self.repo.scar("why_node", w))

    def test_erased_things_stay_out_of_every_live_listing(self):
        w = self._root()
        c = self._conv()
        for kind, ref in (("why_node", w), ("conversation", c)):
            self.repo.archive_knowledge(kind, ref, _T1)
            self.repo.erase_knowledge(kind, ref, _T2)
        self.assertEqual([x.id for x in self.repo.list_why_nodes()], [])
        self.assertEqual([x.id for x in self.repo.list_conversations()], [])
        self.assertEqual(self.repo._inventory_rows(), [])
        self.assertEqual(self.repo.list_field_attractors(), [])

    def test_erased_things_leave_the_remnant_list_too(self):
        """遺骸清單是「可以復原的東西」——抹除過的不該還列在那裡誘人去按。"""
        w = self._root()
        self.repo.archive_knowledge("why_node", w, _T1)
        self.repo.erase_knowledge("why_node", w, _T2)
        self.assertEqual(self.repo.archived_items(), [])


class TestWhoPointsAtIt(_Base):
    """FR-004：抹除前說出誰指著它。

    ⚠️ 這個專案被同一件事咬過：把明顯壞掉的指標變成**自信地指錯**的指標。
    """

    def test_lists_the_things_that_point_at_it(self):
        c = self._conv()
        w = self._root(cid=c)
        aid = self.repo.save_article("t", "標題", "內文", root_ids=[w])
        self.repo.archive_knowledge("why_node", w, _T1)
        refs = self.repo.pointers_to("why_node", w)
        self.assertIn(("article", aid), [(x["kind"], x["ref"]) for x in refs])
        self.assertIn(("conversation", c), [(x["kind"], x["ref"]) for x in refs])

    def test_says_nothing_when_nothing_points_at_it(self):
        w = self._root()
        self.repo.archive_knowledge("why_node", w, _T1)
        self.assertEqual(self.repo.pointers_to("why_node", w), [])


class TestEraseDomain(_Base):
    """FR-005：⚠️ 不做第二次死的串聯。"""

    def test_erasing_a_domain_does_not_erase_its_archived_contents(self):
        w = self._root()
        self.repo.set_knowledge_domain("why_node", w, self.gen)
        self.repo.archive_domain(self.gen, _T1)
        self.repo.erase_domain(self.gen, _T2)
        self.assertIsNone(self.repo.scar("why_node", w), "把底下的知識也抹除了")
        self.assertIn(("why_node", w), [(x["kind"], x["ref"]) for x in self.repo.archived_items()])

    def test_its_contents_can_still_be_restored_individually(self):
        w = self._root()
        self.repo.set_knowledge_domain("why_node", w, self.gen)
        self.repo.archive_domain(self.gen, _T1)
        self.repo.erase_domain(self.gen, _T2)
        self.repo.restore_knowledge("why_node", w)
        self.assertIn(w, [x.id for x in self.repo.list_why_nodes()])
        self.assertIsNone(self.repo.knowledge_domain("why_node", w),
                          "復原到一個已被抹除的領域裡了——那個位置的名字已經不存在")

    def test_cannot_erase_a_live_domain(self):
        with self.assertRaises(ValueError):
            self.repo.erase_domain(self.gen, _T2)


if __name__ == "__main__":
    unittest.main()
