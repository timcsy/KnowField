"""spec 070：領域頁的鄰居與岔路。

⚠️ 判準：**如果這個介面給你的東西，搜尋也給得了，它就不該存在。**
搜尋給不了的是**副作用**——你會看到你沒在找的。這三塊就是那個副作用。
"""
import unittest
from datetime import datetime, timezone

from knowfield.organize.neighbours import domain_context
from knowfield.store.repository import Repository
from tests.web_helpers import temp_db

_NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.r = Repository(self.db)
        self.a = self.r.create_domain("A 區", None)
        self.b = self.r.create_domain("B 區", None)
        # A 區：一段互動 ＋ 兩條從它冊封的理解
        self.cid = self.r.save_conversation("A 的互動", [{"role": "user", "content": "x"}], None)
        self.w1 = self.r.add_why_node("A 的理解一", [], [], False, 0, _NOW, conversation_id=self.cid)
        self.w2 = self.r.add_why_node("A 的理解二", [], [], False, 0, _NOW, conversation_id=self.cid)
        for w in (self.w1, self.w2):
            self.r.anoint_why_node(w)
        self.r.set_knowledge_domain("conversation", self.cid, self.a)
        self.r.set_knowledge_domain("why_node", self.w1, self.a)
        # ⚠️ 理解二放到 B 區 ⇒ 這條「理解→互動」的邊**跨區**了，那就是岔路
        self.r.set_knowledge_domain("why_node", self.w2, self.b)

    def tearDown(self):
        self.r.close()


class TestCrossings(Base):
    def test_counts_only_cross_domain_links(self):
        ctx = domain_context(self.r, self.a, None)
        by = {c["domain_id"]: c["count"] for c in ctx["crossings"]}
        self.assertEqual(by.get(self.b), 1, f"跨區連結算錯：{ctx['crossings']}")
        self.assertNotIn(self.a, by, "同區的被算成岔路了——那不是岔路")

    def test_names_the_other_side(self):
        ctx = domain_context(self.r, self.a, None)
        self.assertEqual(ctx["crossings"][0]["name"], "B 區")

    def test_works_without_vectors(self):
        """⚠️ FR-005：沒有向量時 ⛓ 照樣要有值——
        三塊一起失效比少一塊更糟：你會以為這一區真的沒有鄰居。"""
        ctx = domain_context(self.r, self.a, None)
        self.assertTrue(ctx["crossings"])
        self.assertFalse(ctx["has_geometry"], "沒有向量卻宣稱算得出幾何")
        self.assertEqual(ctx["fringe"], [])
        self.assertEqual(ctx["nearby"], [])


class _Emb:
    """⚠️ 只用來決定 tag——`domain_context` **不呼叫 API**。

    逛一頁不該花錢也不該等，所以幾何只用**已經落庫**的向量。
    測試因此要自己種向量，而那正好逼我們把這個設計寫下來。
    """
    tag = "t"


class TestGeometry(Base):
    def _vec(self, entry_id, v):
        import json
        self.r.conn.execute(
            "INSERT INTO entry_embeddings (entry_id, tag, dim, vector_json)"
            " VALUES (%s,'t',%s,%s)", (entry_id, len(v), json.dumps(v)))
        self.r.conn.commit()

    def test_fringe_is_sorted_far_first(self):
        odd = self.r.add_why_node("B 的東西混進來", [], [], False, 0, _NOW)
        self.r.anoint_why_node(odd)
        self.r.set_knowledge_domain("why_node", odd, self.a)
        self._vec(-self.w1, [1.0, 0.0, 0.0])
        self._vec(-odd, [0.0, 1.0, 0.0])
        ctx = domain_context(self.r, self.a, _Emb())
        self.assertTrue(ctx["has_geometry"])
        self.assertTrue(ctx["fringe"])
        ds = [f["dist"] for f in ctx["fringe"]]
        self.assertEqual(ds, sorted(ds, reverse=True), "邊陲沒有由遠而近排")
        self.assertEqual(ctx["fringe"][0]["ref"], odd, "最該掉出去的不是排最前")

    def test_nearby_excludes_self(self):
        self._vec(-self.w1, [1.0, 0.0, 0.0])
        self._vec(-self.w2, [0.0, 1.0, 0.0])
        ctx = domain_context(self.r, self.a, _Emb())
        self.assertNotIn(self.a, [n["domain_id"] for n in ctx["nearby"]])


if __name__ == "__main__":
    unittest.main()
