"""spec 065：建議怎麼整理。

⚠️ 這一刀最容易做壞的地方不是「建議得準不準」，是**理由能不能被反駁**。
一個不可反駁的理由（「它們都跟 X 有關」）會讓介面被橡皮圖章化——
所以測試驗的是**理由指得出具體的那條邊**，不是建議的品質。
"""
import unittest
from datetime import datetime, timezone

from knowfield.organize.suggest import structural_groups, suggest_folders
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.r = Repository(self.db)
        # 兩段互動，各冊封出幾條理解 ⇒ 兩個**結構上**的群
        self.c1 = self.r.save_conversation("Flow Matching 的底層", [{"role": "user", "content": "a"}], None)
        self.c2 = self.r.save_conversation("Actor Model 怎麼看", [{"role": "user", "content": "b"}], None)
        self.w1 = [self._why(f"FM 理解 {i}", self.c1) for i in range(3)]
        self.w2 = [self._why(f"Actor 理解 {i}", self.c2) for i in range(2)]
        self.lone = self._why("一條孤零零的理解", None)

    def tearDown(self):
        self.r.close()

    def _why(self, claim, cid):
        wid = self.r.add_why_node(claim, [], [], False, 0, _NOW, conversation_id=cid)
        self.r.anoint_why_node(wid)
        return wid


class TestStructuralGroups(Base):
    def test_groups_come_from_real_edges(self):
        g = structural_groups(self.r)
        by = {x["reason"]: x for x in g}
        self.assertTrue(any("Flow Matching 的底層" in k for k in by), f"看到的是 {list(by)}")
        self.assertTrue(any("Actor Model 怎麼看" in k for k in by))

    def test_every_reason_names_a_concrete_edge(self):
        """⚠️ 判準①：理由要**指得出那條邊**，不是主題標籤。

        （落單那一群除外——它的理由是「**沒有**任何連結」，那本身也可查證：
        你可以去確認它們真的沒有邊。）
        """
        for x in [g for g in structural_groups(self.r) if not g.get("lonely")]:
            self.assertTrue(x.get("edge"), f"這一群沒有指出邊：{x['reason']}")
            kind, ref = x["edge"]
            self.assertIn(kind, ("conversation", "source"))
            self.assertIsNotNone(ref)

    def test_a_group_carries_its_own_source_conversation(self):
        """由來那段互動本身也要被搬進去——不然理解進了資料夾，它的由來留在外面。"""
        g = [x for x in structural_groups(self.r) if "Flow Matching" in x["reason"]][0]
        self.assertIn(("conversation", self.c1), [(i["kind"], i["ref"]) for i in g["items"]])
        self.assertEqual(len([i for i in g["items"] if i["kind"] == "why_node"]), 3)

    def test_lonely_items_are_set_aside_not_forced(self):
        """FR-005：⚠️ **允許留白**——分不出來的不硬分。"""
        g = structural_groups(self.r)
        lone = [x for x in g if x.get("lonely")]
        self.assertEqual(len(lone), 1)
        self.assertIn(("why_node", self.lone), [(i["kind"], i["ref"]) for i in lone[0]["items"]])

    def test_already_filed_things_do_not_appear(self):
        """⚠️ 驗收 3：只整理**未歸屬**的。"""
        did = self.r.create_domain("已經有的領域", None)
        self.r.set_knowledge_domain("why_node", self.w1[0], did)
        self.r.set_knowledge_domain("conversation", self.c1, did)
        refs = [(i["kind"], i["ref"]) for x in structural_groups(self.r) for i in x["items"]]
        self.assertNotIn(("why_node", self.w1[0]), refs)
        self.assertNotIn(("conversation", self.c1), refs)


class _OfflineChat:
    """離線後端：reply 一律拋——驗 FR-003 的退路。"""

    def reply(self, messages):
        raise RuntimeError("離線")


class TestFoldersFallBackToStructure(Base):
    def test_llm_failure_still_returns_groups(self):
        """FR-003：LLM 掛掉 → 退回結構群，**不是回空的**。"""
        folders = suggest_folders(self.r, _OfflineChat())
        self.assertTrue(folders, "LLM 失敗就回空的——那會讓使用者以為『沒東西可整理』")
        for f in folders:
            self.assertTrue(f["reasons"], "退回結構群之後理由不見了")

    def test_lonely_group_is_marked_do_not_split(self):
        folders = suggest_folders(self.r, _OfflineChat())
        lonely = [f for f in folders if f.get("lonely")]
        self.assertEqual(len(lonely), 1)
        self.assertFalse(lonely[0].get("suggest_apply", True),
                         "落單那一群不該被建議套用——留白比硬分好")


class _FakeChat:
    """假 LLM：把兩群合成一夾，驗合併路徑。"""

    def __init__(self, out):
        self.out = out
        self.seen = None

    def reply(self, messages):
        self.seen = messages
        return self.out


class TestLLMMayOnlyRegroup(Base):
    def test_llm_can_merge_groups(self):
        ids = [g["id"] for g in structural_groups(self.r) if not g.get("lonely")]
        chat = _FakeChat(f"夾：生成模型｜{','.join(ids)}｜-")
        folders = [f for f in suggest_folders(self.r, chat) if not f.get("lonely")]
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0]["name"], "生成模型")
        self.assertEqual(len(folders[0]["reasons"]), 2, "合併之後兩群的理由都要留著")

    def test_llm_cannot_invent_items(self):
        """⚠️ FR-002：LLM 只能重組**群**。它指一個不存在的群 → 忽略，不是憑空生東西。"""
        chat = _FakeChat("夾：亂編的｜g-does-not-exist｜-")
        folders = [f for f in suggest_folders(self.r, chat) if not f.get("lonely")]
        for f in folders:
            self.assertTrue(f["items"], f"{f['name']} 是空夾")

    def test_prompt_does_not_leak_frequency_signals(self):
        """⚠️ FR-006：馬太陷阱——熱門度不進提示，也就不可能進排序。"""
        chat = _FakeChat("夾：X｜g1｜-")
        suggest_folders(self.r, chat)
        blob = " ".join(m["content"] for m in (chat.seen or []))
        for word in ("熱門", "採用次數", "最多人", "popular"):
            self.assertNotIn(word, blob)


if __name__ == "__main__":
    unittest.main()


class TestApi(unittest.TestCase):
    """API 層：⚠️ FR-004——**沒有任何一次套用多夾的路徑**。"""

    def setUp(self):
        from fastapi.testclient import TestClient
        self.db = temp_db()
        self.app = build_app(self.db)
        self.app.state.suggest_backend_factory = lambda: _OfflineChat()
        self.c = TestClient(self.app)
        r = Repository(self.db)
        cid = r.save_conversation("某段互動", [{"role": "user", "content": "x"}], None)
        for i in range(3):
            w = r.add_why_node(f"理解 {i}", [], [], False, 0, _NOW, conversation_id=cid)
            r.anoint_why_node(w)
        r.close()

    def test_suggest_returns_folders_with_reasons(self):
        d = self.c.get("/api/domains/suggest").json()
        self.assertTrue(d["folders"])
        for f in d["folders"]:
            self.assertTrue(f["reasons"])

    def test_apply_one_folder_creates_and_moves(self):
        f = [x for x in self.c.get("/api/domains/suggest").json()["folders"]
             if x.get("suggest_apply")][0]
        r = self.c.post("/api/domains/suggest/apply",
                        json={"name": "生成模型", "items": f["items"]})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["moved"], len(f["items"]))
        repo = Repository(self.db)
        names = [d["name"] for d in repo.list_domains()]
        left = [x for x in repo._inventory_rows() if x["domain_id"] is None]
        repo.close()
        self.assertIn("生成模型", names)
        self.assertEqual(left, [], "套用之後還有東西留在根領域")

    def test_apply_rejects_empty(self):
        r = self.c.post("/api/domains/suggest/apply", json={"name": "空的", "items": []})
        self.assertEqual(r.status_code, 400)

    def test_there_is_no_apply_all_route(self):
        """⚠️ 這條測試守的是**設計**，不是行為：一旦有人加了批次套用，它會紅。"""
        paths = {getattr(r, "path", "") for r in self.app.routes}
        for p in paths:
            self.assertNotIn("apply-all", p)
            self.assertNotIn("apply_all", p)
        applies = [p for p in paths if "suggest" in p and "apply" in p]
        self.assertEqual(applies, ["/api/domains/suggest/apply"],
                         f"多了套用路徑：{applies}")


class TestReasonsAreReadable(Base):
    """⚠️ 理由是**要被讀的**——量詞錯了、markdown 漏出來，都會讓人覺得這句是機器湊的
    ⇒ 不可信 ⇒ 不會細看 ⇒ 介面就被橡皮圖章化了。判準①靠的就是這句話被真的讀。"""

    def test_singular_reads_naturally(self):
        r = Repository(temp_db())
        cid = r.save_conversation("只有一條的互動", [{"role": "user", "content": "x"}], None)
        w = r.add_why_node("唯一那條", [], [], False, 0, _NOW, conversation_id=cid)
        r.anoint_why_node(w)
        reasons = [g["reason"] for g in structural_groups(r)]
        r.close()
        self.assertTrue(any("這條理解是從" in x for x in reasons), reasons)
        self.assertFalse(any("這 1 條" in x for x in reasons), reasons)

    def test_no_markdown_leaks_into_reasons(self):
        for g in structural_groups(self.r):
            self.assertNotIn("**", g["reason"], f"markdown 漏到理由裡：{g['reason']}")
