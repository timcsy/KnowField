"""spec 055：封存＝離開活的場，留下遺骸。**一個通用動作**，領域與知識都適用。

使用者的比喻：超新星爆炸 · 黑洞 · 細胞凋亡——共同點是**結束不等於湮滅**。

⚠️ 本刀唯一會沉默失敗的地方：**封存必須擋住檢索，不只擋住畫面**。
只在清單頁過濾、沒擋住 RAG／聊天脈絡的話，封存過的知識**仍在影響每一個回答**，
而且沒有任何跡象——使用者以為它退場了。下面那支 sweep 測試就是為了它而寫。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db

_M = [{"role": "user", "content": "嗨"}]
_NOW = "2026-08-26T12:00:00Z"
_URL = "https://example.com/paper"


class _Base(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())
        self.ai = self.repo.create_domain("AI")
        self.gen = self.repo.create_domain("生成模型", self.ai)
        self.flow = self.repo.create_domain("Flow Matching", self.gen)

    def tearDown(self):
        self.repo.close()

    def _conv(self, domain=None):
        return self.repo.autosave_temporary(None, _M, _NOW, domain_id=domain)

    def _root(self, claim="理解", domain=None, entry=0):
        r = self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, domain_id, source_entry_id)"
            " VALUES (%s,'推論','anointed',%s,%s) RETURNING id",
            (claim, domain, entry)).fetchone()
        self.repo.conn.commit()
        return int(r["id"])

    def _seed_source(self, domain=None):
        # ⚠️ 種子容器的 date 是哨兵 `SEEDS_DATE`，不是真日期——用錯的話
        #    `list_seeds()` 回空集合，而測試會在一個**空集合**上通過（我第一版就是）。
        from knowfield.config import SEEDS_DATE
        d = self.repo.conn.execute(
            "INSERT INTO digests (date) VALUES (%s) RETURNING id", (SEEDS_DATE,)).fetchone()
        for i in (1, 2):
            self.repo.conn.execute(
                "INSERT INTO digest_entries (digest_id, rank, title, url, domain_id)"
                " VALUES (%s,%s,'某篇論文',%s,%s)", (int(d["id"]), i, _URL, domain))
        self.repo.conn.commit()
        return _URL


class TestArchiveKnowledge(_Base):
    """封存一則知識。"""

    def test_archived_root_leaves_the_live_list(self):
        w = self._root()
        self.repo.archive_knowledge("why_node", w, _NOW)
        self.assertNotIn(w, [x.id for x in self.repo.list_why_nodes("anointed")])

    def test_the_remnant_is_queryable(self):
        w = self._root("這條會被封存")
        self.repo.archive_knowledge("why_node", w, _NOW)
        a = self.repo.archived_items()
        self.assertEqual([(x["kind"], x["ref"]) for x in a], [("why_node", w)])
        self.assertIn("這條會被封存", a[0]["label"])
        self.assertEqual(a[0]["archived_at"], _NOW)

    def test_restore_brings_it_back(self):
        w = self._root()
        self.repo.archive_knowledge("why_node", w, _NOW)
        self.repo.restore_knowledge("why_node", w)
        self.assertIn(w, [x.id for x in self.repo.list_why_nodes("anointed")])
        self.assertEqual(self.repo.archived_items(), [])

    # ⚠️ FR-004：擋住檢索，不只擋住畫面 ────────────────────────────

    def test_archived_root_leaves_the_attractor_corpus(self):
        """⚠️ 場的吸引子＝餵給聊天與 RAG 的東西。沒擋住這裡，封存就只是「畫面上不見」。"""
        w = self._root("這條不該再影響回答")
        before = len(self.repo.list_field_attractors())
        self.repo.archive_knowledge("why_node", w, _NOW)
        after = self.repo.list_field_attractors()
        self.assertEqual(len(after), before - 1, "封存過的理解還在吸引子語料裡")
        self.assertNotIn("這條不該再影響回答", " ".join(c.body or "" for c in after))

    def test_archived_source_leaves_the_seed_corpus(self):
        url = self._seed_source()
        before = len(self.repo.list_seeds())
        self.assertEqual(before, 2, "fixture 沒真的種進種子容器——那樣測的是空集合")
        self.repo.archive_knowledge("source", url, _NOW)
        self.assertEqual(len(self.repo.list_seeds()), before - 2, "封存過的來源還在種子語料裡")

    # FR-003：不出現在任何活的清單 ─────────────────────────────────

    def test_archived_things_vanish_from_every_live_listing(self):
        """⚠️ Sweep：一種一件，封存後**每一份活的清單都不該有它**。

        少過濾一處就是沉默失敗——那一處會繼續把遺骸當成活的。
        """
        c = self._conv(self.gen)
        w = self._root(domain=self.gen)
        aid = self.repo.save_article("t", "標題", "內文")
        url = self._seed_source(self.gen)
        for kind, ref in (("conversation", c), ("why_node", w),
                          ("article", aid), ("source", url)):
            self.repo.archive_knowledge(kind, ref, _NOW)

        self.assertEqual([x.id for x in self.repo.list_conversations()], [])
        self.assertEqual([x.id for x in self.repo.list_why_nodes("anointed")], [])
        self.assertEqual(self.repo.list_articles(), [])
        self.assertEqual(self.repo.list_source_groups(), [])
        self.assertEqual(self.repo._inventory_rows(), [])
        self.assertEqual(self.repo.domain_view(None)["items"], [])
        self.assertEqual(self.repo.list_field_attractors(), [])


class TestArchiveDomain(_Base):
    """封存一個領域：**整棵子樹一起成為遺骸**（使用者裁決：不上移）。"""

    def test_the_whole_subtree_is_archived_together(self):
        c = self._conv(self.gen)
        w = self._root(domain=self.flow)
        self.repo.archive_domain(self.gen, _NOW)
        live = [d["id"] for d in self.repo.list_domains()]
        self.assertEqual(live, [self.ai], "子領域沒有跟著封存")
        self.assertEqual(self.repo._inventory_rows(), [], "底下的知識沒有跟著封存")
        self.assertEqual(self.repo.knowledge_domain("conversation", c), self.gen,
                         "⚠️ 知識被搬去父領域了——使用者要的是跟著封存，不是上移")
        self.assertEqual(self.repo.knowledge_domain("why_node", w), self.flow)

    def test_restoring_brings_the_same_batch_back(self):
        c = self._conv(self.gen)
        w = self._root(domain=self.flow)
        self.repo.archive_domain(self.gen, _NOW)
        self.repo.restore_domain(self.gen)
        self.assertEqual({d["id"] for d in self.repo.list_domains()},
                         {self.ai, self.gen, self.flow})
        self.assertEqual(len(self.repo._inventory_rows()), 2)
        self.assertEqual(self.repo.knowledge_domain("conversation", c), self.gen)

    def test_restoring_does_not_drag_back_things_archived_separately(self):
        """⚠️ 只復原**同一批**：自己被單獨封存的東西不該搭順風車回來。"""
        c = self._conv(self.gen)
        w = self._root(domain=self.gen)
        self.repo.archive_knowledge("why_node", w, "2026-08-25T00:00:00Z")   # 先自己被封
        self.repo.archive_domain(self.gen, _NOW)
        self.repo.restore_domain(self.gen)
        self.assertIn(c, [x.id for x in self.repo.list_conversations()])
        self.assertNotIn(w, [x.id for x in self.repo.list_why_nodes("anointed")],
                         "把不屬於這一批的東西也復原了")

    def test_the_domain_leaves_the_live_tree_but_stays_queryable(self):
        self.repo.archive_domain(self.gen, _NOW)
        self.assertNotIn(self.gen, [d["id"] for d in self.repo.list_domains()])
        self.assertIn(self.gen, [d["id"] for d in self.repo.archived_domains()])

    def test_preview_reports_the_whole_subtree(self):
        """⚠️ 這裡跟階段 49 相反：既然整棵子樹會被帶走，就**必須**報整棵子樹。

        報少了才是嚇人——使用者會以為只封一層。
        """
        self._conv(self.gen); self._root(domain=self.flow)
        p = self.repo.archive_domain_preview(self.gen)
        self.assertEqual((p["items"], p["children"]), (2, 1))

    def test_preview_has_no_side_effects(self):
        self.repo.archive_domain_preview(self.gen)
        self.assertIn(self.gen, [d["id"] for d in self.repo.list_domains()])


if __name__ == "__main__":
    unittest.main()
