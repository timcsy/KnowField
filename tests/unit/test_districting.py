"""spec 069：行政區。

⚠️ 最重要的一條不是「分得好不好」，是**它永遠不會動已經歸屬的東西**——
實驗量到 ARI ≈ 0.18（換個種子就大幅重排），所以全量重劃會讓大量地址改變。
⇒ 那個禁令必須是**結構上的**（沒有那條路），不是紀律上的（記得不要）。
"""
import unittest
from datetime import datetime, timezone

from knowfield.organize.district import districts
from knowfield.store.repository import Repository
from tests.web_helpers import temp_db

_NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Emb:
    """離線 embedder：把文字映到一個可預測的小空間，好讓分群結果可斷言。"""

    def embed_many(self, texts):
        return [self.embed(t) for t in texts]

    def embed(self, text):
        # 三個關鍵字 → 三個正交方向；其餘落在原點附近
        keys = ("貓", "船", "樹")
        v = [0.01, 0.01, 0.01]
        for i, k in enumerate(keys):
            if k in text:
                v[i] = 1.0
        return v


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.r = Repository(self.db)
        self.ids = {}
        for word in ("貓", "船", "樹"):
            for i in range(4):
                w = self.r.add_why_node(f"{word}的理解 {i}", [], [], False, 0, _NOW)
                self.r.anoint_why_node(w)
                self.ids[(word, i)] = w

    def tearDown(self):
        self.r.close()


class TestNeverTouchesAssigned(Base):
    """⚠️ 本檔存在的主要理由（FR：驗收 2）。"""

    def test_already_filed_never_appears(self):
        did = self.r.create_domain("我自己放的", None)
        keep = self.ids[("貓", 0)]
        self.r.set_knowledge_domain("why_node", keep, did)
        refs = [i["ref"] for d in districts(self.r, _Emb()) for i in d["items"]]
        self.assertNotIn(keep, refs, "已經有地址的東西被重新劃了——那就是全量重劃")

    def test_everything_unfiled_gets_a_district(self):
        got = {i["ref"] for d in districts(self.r, _Emb()) for i in d["items"]}
        self.assertEqual(got, set(self.ids.values()), "有東西沒拿到地址")


class TestShape(Base):
    def test_regions_are_balanced(self):
        ds = districts(self.r, _Emb(), k=3)
        sizes = sorted(len(d["items"]) for d in ds)
        self.assertGreaterEqual(sizes[0], 2, f"有畸零區：{sizes}")
        self.assertLessEqual(sizes[-1], 8, f"有巨無霸區：{sizes}")

    def test_similar_things_land_together(self):
        ds = districts(self.r, _Emb(), k=3)
        where = {i["ref"]: n for n, d in enumerate(ds) for i in d["items"]}
        for word in ("貓", "船", "樹"):
            regions = {where[self.ids[(word, i)]] for i in range(4)}
            self.assertEqual(len(regions), 1, f"「{word}」被拆散到 {regions}")

    def test_each_region_has_a_checkable_reason(self):
        """⚠️ FR-005：理由要**可判斷**——列得出錨與代表成員，分數不算理由。"""
        for d in districts(self.r, _Emb(), k=3):
            self.assertTrue(d["anchor"], "沒有錨")
            self.assertTrue(d["reasons"], "沒有理由")
            joined = " ".join(d["reasons"])
            self.assertNotIn("0.", joined, "理由裡出現了分數——那是不可反駁的東西")

    def test_display_name_is_short(self):
        """⚠️ 實驗印出的區名是一整句主張，完全不能當資料夾名。"""
        for d in districts(self.r, _Emb(), k=3):
            self.assertLessEqual(len(d["name"]), 24, f"區名太長：{d['name']}")


class TestFallback(unittest.TestCase):
    def test_no_embedder_falls_back_to_edges(self):
        """FR：驗收 4——沒有向量時退回既有的邊，**不是回空的**。"""
        db = temp_db()
        r = Repository(db)
        cid = r.save_conversation("某段互動", [{"role": "user", "content": "x"}], None)
        for i in range(3):
            w = r.add_why_node(f"理解 {i}", [], [], False, 0, _NOW, conversation_id=cid)
            r.anoint_why_node(w)
        out = districts(r, None)
        r.close()
        self.assertTrue(out, "沒有 embedder 就回空的——那是把故障畫成結論")


if __name__ == "__main__":
    unittest.main()


class TestMixedDimensionsIsRefused(Base):
    """⚠️ 把 256 維的 stub 混進 1536 維的真實向量，結果是**看起來正常的垃圾**。

    實驗時真的差點發生（`make_embedder(Config())` 回的是離線 stub）。
    ⇒ 寧可退回既有的邊分群，也不要算一個沒有意義的距離。
    """

    def test_mixed_dims_falls_back(self):
        class Mixed:
            def embed_many(self, texts):
                return [[0.1] * (3 if i % 2 else 9) for i, _ in enumerate(texts)]
            def embed(self, t):
                return [0.1] * 3
        out = districts(self.r, Mixed())
        for d in out:
            joined = " ".join(d["reasons"])
            self.assertNotIn("都最靠近", joined, "維度不一致還照算了")


class TestAssignedBy(Base):
    """FR-007：⚠️ **人的 override 要看得出來**——否則你會把機器的猜測當成自己的判斷。"""

    def test_machine_assignment_is_marked(self):
        did = self.r.create_domain("算出來的", None)
        self.r.batch_move([("why_node", self.ids[("貓", 0)])], did, by="machine")
        row = self.r.conn.execute("SELECT assigned_by FROM why_nodes WHERE id=%s",
                                  (self.ids[("貓", 0)],)).fetchone()
        self.assertEqual(row["assigned_by"], "machine")

    def test_human_override_is_marked_and_wins(self):
        did = self.r.create_domain("算出來的", None)
        mine = self.r.create_domain("我搬過去的", None)
        wid = self.ids[("船", 0)]
        self.r.batch_move([("why_node", wid)], did, by="machine")
        self.r.set_knowledge_domain("why_node", wid, mine)          # 預設 human
        row = self.r.conn.execute("SELECT domain_id, assigned_by FROM why_nodes WHERE id=%s",
                                  (wid,)).fetchone()
        self.assertEqual(row["domain_id"], mine)
        self.assertEqual(row["assigned_by"], "human", "人搬過之後還標著 machine")


class TestNamesHavePruningPower(Base):
    """⚠️ 分群命名的經典退化：LLM 最省力的答案永遠是**共有的最泛的詞**。

    判準（knowie 判斷真／假母概念用的同一把尺）：
    **一個名字如果可以套在任何一群上，它就沒有修剪力。**
    光在 prompt 裡講不夠——要擋。
    """

    def test_generic_names_are_rejected(self):
        class Lazy:
            def reply(self, messages):
                return "AI"
        for d in districts(self.r, _Emb(), k=3, chat=Lazy()):
            self.assertNotEqual(d["name"], "AI", "泛詞被當成區名了")
