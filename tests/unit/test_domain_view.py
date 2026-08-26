"""spec 052：一個領域的視野——含子孫，而「通往外面」相對於立足點。

⚠️ 核心：**糾纏是 `(邊, 立足點)` 的屬性，不是那條邊的固有屬性。**
一條 `Flow Matching → 數學` 的邊，站在 Flow Matching 看是跨出去；
站在 AI 看，兩端都在我的子樹裡 ⇒ **它是內部連結**。
把它算成固有屬性的話，站在祖先會看到一堆其實在自己家裡的「外部連結」。
"""
import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db

_M = [{"role": "user", "content": "嗨"}]


class TestDomainView(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(temp_db())
        self.ai = self.repo.create_domain("AI")
        self.gen = self.repo.create_domain("生成模型", self.ai)
        self.flow = self.repo.create_domain("Flow Matching", self.gen)
        self.math = self.repo.create_domain("數學", self.ai)
        self.bio = self.repo.create_domain("生物")

    def tearDown(self):
        self.repo.close()

    def _conv(self, domain=None):
        return self.repo.autosave_temporary(None, _M, "2026-08-26T00:00:00Z", domain_id=domain)

    def _root(self, claim, cid=None, domain=None):
        r = self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, conversation_id, domain_id)"
            " VALUES (%s,'推論','anointed',%s,%s) RETURNING id", (claim, cid, domain)).fetchone()
        self.repo.conn.commit()
        return int(r["id"])

    # ── FR-002：視野含子孫 ──────────────────────────────────────

    def test_view_includes_descendants(self):
        self._conv(self.flow); self._conv(self.gen)
        v = self.repo.domain_view(self.ai)
        self.assertEqual(len([i for i in v["items"] if i["kind"] == "conversation"]), 2)

    def test_view_of_a_leaf_domain_is_only_its_own(self):
        self._conv(self.flow); self._conv(self.math)
        v = self.repo.domain_view(self.flow)
        self.assertEqual(len(v["items"]), 1)

    def test_standing_at_root_sees_everything(self):
        self._conv(self.flow); self._conv(self.bio); self._conv(None)
        v = self.repo.domain_view(None)
        self.assertEqual(len(v["items"]), 3, "站在根＝看到全部，跨領域視野就是往上站一層")

    def test_children_are_immediate_only(self):
        """子領域列**直屬**的，不是全部子孫——不然側欄會塌成一張平表。"""
        v = self.repo.domain_view(self.ai)
        self.assertEqual({c["name"] for c in v["children"]}, {"生成模型", "數學"})

    # ── FR-003：通往外面相對於立足點 ─────────────────────────────

    def test_edge_leaving_my_subtree_counts(self):
        c = self._conv(self.flow)
        w = self._root("住在數學的理解", c, self.math)
        v = self.repo.domain_view(self.flow)
        self.assertEqual([(o["kind"], o["ref"]) for o in v["outward"]], [("why_node", w)])

    def test_the_same_edge_is_internal_from_the_ancestor(self):
        """⚠️ 同一條邊，站在 AI 看兩端都在我家裡 ⇒ **不算**通往外面。"""
        c = self._conv(self.flow)
        self._root("住在數學的理解", c, self.math)
        v = self.repo.domain_view(self.ai)
        self.assertEqual(v["outward"], [], f"把 (邊,立足點) 當成邊的固有屬性了：{v['outward']}")

    def test_root_sees_nothing_outward(self):
        """站在根，沒有「外面」可言。"""
        c = self._conv(self.flow)
        self._root("理解", c, self.math)
        self.assertEqual(self.repo.domain_view(None)["outward"], [])

    def test_edge_to_root_domain_is_not_outward(self):
        """對方還在根領域 ＝ 還沒被放過，不是「在外面」（同 spec 050/051 的區分）。"""
        c = self._conv(self.flow)
        self._root("還沒歸位的理解", c, None)
        self.assertEqual(self.repo.domain_view(self.flow)["outward"], [])

    def test_outward_is_deduped(self):
        """同一個外部鄰居被我這邊兩件東西連著 → 只列一次。"""
        c1, c2 = self._conv(self.flow), self._conv(self.flow)
        w = self._root("外面的理解", c1, self.math)
        aid = self.repo.save_article("t", "b", "zh", root_ids=[w], conversation_id=c2)
        self.repo.set_knowledge_domain("article", aid, self.flow)
        refs = [(o["kind"], o["ref"]) for o in self.repo.domain_view(self.flow)["outward"]]
        self.assertEqual(refs.count(("why_node", w)), 1, f"沒去重：{refs}")

    def test_outward_says_where_the_other_end_lives(self):
        c = self._conv(self.flow)
        self._root("理解", c, self.math)
        o = self.repo.domain_view(self.flow)["outward"][0]
        self.assertEqual(o["domain_id"], self.math, "不說對方住哪，就沒辦法跳過去")


if __name__ == "__main__":
    unittest.main()


class TestChildCounts(unittest.TestCase):
    """⚠️ 側欄的數字要跟「點進去看到的」一致——說謊的數字比沒有數字更糟。"""

    def setUp(self):
        self.repo = Repository(temp_db())
        self.ai = self.repo.create_domain("AI")
        self.gen = self.repo.create_domain("生成模型", self.ai)
        self.flow = self.repo.create_domain("Flow Matching", self.gen)

    def tearDown(self):
        self.repo.close()

    def _conv(self, domain):
        return self.repo.autosave_temporary(None, _M, "2026-08-26T00:00:00Z", domain_id=domain)

    def test_child_count_includes_grandchildren(self):
        self._conv(self.gen); self._conv(self.flow); self._conv(self.flow)
        child = self.repo.domain_view(self.ai)["children"][0]
        self.assertEqual(child["count"], 3, "子領域的數字沒有含它自己的子孫")

    def test_child_count_matches_what_you_see_after_clicking_in(self):
        self._conv(self.gen); self._conv(self.flow)
        child = self.repo.domain_view(self.ai)["children"][0]
        self.assertEqual(child["count"], len(self.repo.domain_view(child["id"])["items"]))


class TestInventoryDates(unittest.TestCase):
    """spec 057：清冊要帶時間，檔案總管才排得了序。

    ⚠️ 四種的時間欄名字**不一樣**——假設同名的話，缺的那幾種會**安靜地**排在最後。
    """

    def setUp(self):
        self.repo = Repository(temp_db())

    def tearDown(self):
        self.repo.close()

    def test_every_kind_carries_a_date(self):
        self.repo.autosave_temporary(None, _M, "2026-08-20T00:00:00Z")
        self.repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, created_at)"
            " VALUES ('理解','推論','anointed','2026-08-21T00:00:00Z')")
        self.repo.save_article("t", "標題", "內文", created_at="2026-08-22T00:00:00Z")
        d = self.repo.conn.execute(
            "INSERT INTO digests (date) VALUES ('__種子__') RETURNING id").fetchone()
        self.repo.conn.execute(
            "INSERT INTO digest_entries (digest_id, rank, title, url, ingested_at)"
            " VALUES (%s,1,'某來源','https://a/b','2026-08-23')", (int(d["id"]),))
        self.repo.conn.commit()
        rows = self.repo._inventory_rows()
        self.assertEqual(len(rows), 4)
        blank = [r["kind"] for r in rows if not r.get("at")]
        self.assertEqual(blank, [], f"這幾種沒有時間，排序時會安靜地沉底：{blank}")
