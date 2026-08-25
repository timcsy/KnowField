"""spec 049：糾纏 Tangle（spec 050 起走批次路徑——單件操作＝一個元素的清單）

spec 049 原本的 ＝ 樹裝不下的那條連結。

⚠️ 糾纏**在整理之前就存在**——整理只是讓它現形。所以偵測是「查既有連結」，不是「建東西」。

兩條防爆界線，兩條都用測試釘死：
① **只算直接連結**，不算傳遞閉包。66/75 條理解連著對話，搬一段跳 15 條詢問＝那功能沒人用。
② **連帶只走一層**，不遞迴。知識的連結是**網不是樹**，不設界線會搬走半個場。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db

_M = [{"role": "user", "content": "嗨"}]


class TestTangles(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())
        self.a = self.repo.create_domain("A")
        self.b = self.repo.create_domain("B")

    def tearDown(self):
        self.repo.close()

    def _conv(self, domain=None):
        return self.repo.autosave_temporary(None, _M, "2026-08-25T00:00:00Z", domain_id=domain)

    def _root(self, claim, cid=None, domain=None):
        r = self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, conversation_id, domain_id)"
            " VALUES (%s,'推論','anointed',%s,%s) RETURNING id", (claim, cid, domain)).fetchone()
        self.repo.conn.commit()
        return int(r["id"])

    def test_no_tangle_when_same_domain(self):
        c = self._conv(self.a)
        self._root("理解", c, self.a)
        self.assertEqual(self.repo.batch_tangles([("conversation", c)], self.a), [])

    def test_tangle_when_move_would_split(self):
        """搬對話到 B，而它冊封出的理解留在 A → 一條糾纏。"""
        c = self._conv(self.a)
        w = self._root("理解", c, self.a)
        t = self.repo.batch_tangles([("conversation", c)], self.b)
        self.assertEqual([(x["kind"], x["ref"]) for x in t], [("why_node", w)])

    def test_only_direct_edges_not_transitive(self):
        """⚠️ 界線①：理解連著對話、文章連著理解——搬對話時**不該**把文章也算進來。"""
        c = self._conv(self.a)
        w = self._root("理解", c, self.a)
        aid = self.repo.save_article("t", "標題", "內文", root_ids=[w])
        self.repo.set_knowledge_domain("article", aid, self.a)
        t = self.repo.batch_tangles([("conversation", c)], self.b)
        self.assertEqual([x["kind"] for x in t], ["why_node"], "文章是**間接**連的，不該算糾纏")

    def test_article_tangles_are_visible_now(self):
        """前置補的那條斷線：搬文章時看得到它跟哪些理解糾纏。"""
        w1 = self._root("理解1", None, self.a)
        w2 = self._root("理解2", None, self.a)
        aid = self.repo.save_article("t", "標題", "內文", root_ids=[w1, w2])
        self.repo.set_knowledge_domain("article", aid, self.a)
        t = self.repo.batch_tangles([("article", aid)], self.b)
        self.assertEqual(sorted(x["ref"] for x in t), sorted([w1, w2]))

    def test_unassigned_counterpart_is_not_a_tangle(self):
        """⚠️ 對方**未歸屬**時不算糾纏——它還沒有位置，談不上被拆散。"""
        c = self._conv(self.a)
        self._root("理解", c, None)
        self.assertEqual(self.repo.batch_tangles([("conversation", c)], self.b), [])


class TestMoveWithTangles(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())
        self.a = self.repo.create_domain("A")
        self.b = self.repo.create_domain("B")

    def tearDown(self):
        self.repo.close()

    def _setup_chain(self):
        """對話 c → 理解 w → 文章 art，全部在 A。三者串成一條鏈。"""
        c = self.repo.autosave_temporary(None, _M, "2026-08-25T00:00:00Z", domain_id=self.a)
        r = self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, conversation_id, domain_id)"
            " VALUES ('理解','推論','anointed',%s,%s) RETURNING id", (c, self.a)).fetchone()
        w = int(r["id"]); self.repo.conn.commit()
        art = self.repo.save_article("t", "標題", "內文", root_ids=[w])
        self.repo.set_knowledge_domain("article", art, self.a)
        return c, w, art

    def test_bring_along_moves_one_hop_only(self):
        """⚠️ 界線②：連帶只走**一層**。搬對話＋連帶 → 理解跟著走，**文章留在原地**。"""
        c, w, art = self._setup_chain()
        self.repo.batch_move([("conversation", c)], self.b, bring_along=True)
        self.assertEqual(self.repo.get_conversation(c).domain_id, self.b)
        self.assertEqual(self.repo.knowledge_domain("why_node", w), self.b)
        self.assertEqual(self.repo.knowledge_domain("article", art), self.a,
                         "連帶遞迴了——知識的連結是網不是樹，會搬走半個場")

    def test_without_bring_along_only_the_thing_moves(self):
        c, w, _ = self._setup_chain()
        self.repo.batch_move([("conversation", c)], self.b, bring_along=False)
        self.assertEqual(self.repo.get_conversation(c).domain_id, self.b)
        self.assertEqual(self.repo.knowledge_domain("why_node", w), self.a)
