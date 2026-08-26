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
            # 有名字時要短；沒名字時退路可以長一點（它明說了自己是「未命名」）
            if not d["name"].startswith("未命名"):
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


class TestNamingSeesAllRegions(Base):
    """⚠️ 一區一次呼叫的話，LLM 看不到別的區，也就不知道要**排除掉什麼**。

    而「這個名字排除掉了哪些區」正是判斷它有沒有修剪力的方式。
    ⇒ 同一層的兄弟要**一起**命名。
    """

    def test_one_call_that_sees_every_region(self):
        seen = {}

        class Spy:
            def reply(self, messages):
                seen["n"] = seen.get("n", 0) + 1
                seen["body"] = messages[-1]["content"]
                return "0｜甲區\n1｜乙區\n2｜丙區"

        ds = districts(self.r, _Emb(), k=3, chat=Spy())
        self.assertEqual(seen["n"], 1, f"呼叫了 {seen['n']} 次——兄弟沒有一起命名")
        for i in range(len(ds)):
            self.assertIn(f"[{i}]", seen["body"], "有一區沒被送進去")

    def test_samples_cover_breadth_not_just_the_centre(self):
        """⚠️ 只取最靠近中心的，名字會描述**錨附近那幾件**，不是這一區。"""
        seen = {}

        class Spy:
            def reply(self, messages):
                seen["body"] = messages[-1]["content"]
                return ""

        districts(self.r, _Emb(), k=1, chat=Spy())
        # 12 件全部都該出現（k=1 ⇒ 一區裝下全部）
        for word in ("貓", "船", "樹"):
            self.assertIn(word, seen["body"], f"取樣沒涵蓋到「{word}」——只看得到中心附近")

    def test_duplicate_names_are_rejected(self):
        class Same:
            def reply(self, messages):
                return "0｜同一個\n1｜同一個\n2｜同一個"

        names = [d["name"] for d in districts(self.r, _Emb(), k=3, chat=Same())]
        self.assertEqual(len(set(names)), len(names), f"名字重複了：{names}")

    def test_fallback_is_honest_not_a_truncated_sentence(self):
        """⚠️ 「Single Source of Tru」看起來像名字，但它不是。

        一個看起來像名字的錯東西，比一個誠實的空白更糟。
        """
        for d in districts(self.r, _Emb(), k=3, chat=None):
            self.assertTrue(d["name"].startswith("未命名"), f"退路長這樣：{d['name']}")


class TestNamesAreNotJudgedByCode(Base):
    """⚠️ 我加過兩層過濾（泛詞黑名單 ＋「過半數的區都有這個詞」的相對判準）。

    使用者兩次否決：「深度學習沒什麼不好呀」「我覺得不用特別擋名字」。他是對的——
    ① 我量錯了東西：「這個詞在別區出現過」≠「這個名字套在別區上也說得通」；
    ② 名字好不好是**語意判斷**，而**介面本來就讓你改名**——
       後端替你否決等於把裁決搶過去。
    ⇒ 程式只管格式（空的、過長、重名）。
    """

    def test_any_word_the_model_picks_is_kept(self):
        class Term:
            def reply(self, messages):
                # 「理解」出現在每一區的成員文字裡；「AI」曾經被黑名單擋掉
                return "0｜AI\n1｜深度學習\n2｜船的理解"

        names = [d["name"] for d in districts(self.r, _Emb(), k=3, chat=Term())]
        self.assertEqual(sorted(names), ["AI", "深度學習", "船的理解"],
                         "後端還在替使用者否決名字")

    def test_format_is_still_checked(self):
        """格式不是評價：空的、過長、重名仍然擋。"""
        class Bad:
            def reply(self, messages):
                return "0｜\n1｜" + "長" * 40 + "\n2｜好名字"

        names = [d["name"] for d in districts(self.r, _Emb(), k=3, chat=Bad())]
        self.assertIn("好名字", names)
        self.assertEqual(sum(1 for n in names if n.startswith("未命名")), 2)


class TestUnnamedFallsBackNotCollides(Base):
    """⚠️ 模型對兩區都回「未命名」時，去重會把第二個擋掉——
    於是一區顯示裸的「未命名」、另一區顯示退路。兩邊都不好：
    裸字認不出是哪一區，而**取不出名字的原因**才是那時候真正有用的資訊。
    """

    def test_model_saying_unnamed_uses_our_fallback(self):
        class Vague:
            def reply(self, messages):
                return "\n".join(f"{i}｜未命名｜這一區混了太多東西" for i in range(3))

        ds = districts(self.r, _Emb(), k=3, chat=Vague())
        for d in ds:
            self.assertTrue(d["name"].startswith("未命名（"), f"用了裸字：{d['name']}")
            self.assertTrue(any("取不出名字" in x for x in d["reasons"]),
                            "取不出來的原因不見了")
        self.assertEqual(len({d["name"] for d in ds}), 3, "退路撞名了")
