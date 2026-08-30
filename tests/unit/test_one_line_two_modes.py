"""互動與開發之間**只有一條線**：`project_domain_ids()`。

⚠️ 使用者：「不要把開發模式的來源歸換在互動模式的裡面」。
   而它**不只是來源**——對話、理解、應用、子領域全都要照同一條線切。
   ⇒ 判準：**不一致比全有或全無更難察覺**：你會在某一格看到專案的東西、
   在別格看不到，然後以為是資料掉了。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.ingest.service import ContentIngestService
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class _FakeEmb:
    def embed_many(self, texts):
        return [[float(len(t) % 7), 1.0, 0.0] for t in texts]

    def embed(self, text):
        return self.embed_many([text])[0]


class Base(unittest.TestCase):
    """一個專案領域（四種知識各一件）＋ 你自己的（四種各一件）。"""

    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)
        r = Repository(self.db)
        svc = ContentIngestService(r, _FakeEmb(), None)
        self.mine = r.create_domain("我的領域")
        self.pdid = r.create_domain("Demo")
        self.bid = r.add_ext_base("timcsy/Demo")
        r.set_ext_domain(self.bid, self.pdid)
        for did, url, claim, topic in (
                (self.mine, "https://example.com/mine", "我自己的判準", "我的應用"),
                (self.pdid, "github://timcsy/Demo/knowledge/experience.md",
                 "借來的判準", "專案的應用")):
            svc._ingest_markdown("一段內容。", "t", url)
            r.set_knowledge_domain("source", url, did, by="machine")
            w = r.add_why_node(claim, [], [], False, 0, "2026-08-27T00:00:00Z")
            r.anoint_why_node(w)
            r.set_knowledge_domain("why_node", w, did, by="human")
            # ⚠️ 內容要不一樣——`save_conversation` 是**指紋冪等**的，
            #    兩段一樣的對話會回同一個 id，然後第二次歸屬把第一段搬走
            cid = r.save_conversation(f"{topic}的對話", [{"role": "user", "content": topic}])
            r.set_knowledge_domain("conversation", cid, did, by="human")
            aid = r.save_article(topic, topic, f"# {topic}", conversation_id=cid)
            r.set_knowledge_domain("article", aid, did, by="human")
        r.close()

    def repo(self):
        return Repository(self.db)


class TestTheLineIsOne(Base):
    def test_project_domain_ids_is_the_only_predicate(self):
        r = self.repo()
        self.assertEqual(r.project_domain_ids(), {self.pdid})
        r.close()

    def test_sub_domains_of_a_project_count_too(self):
        """⚠️ 只擋那一個領域、不擋子孫的話，往下分一層就漏回思考模式了。"""
        r = self.repo()
        sub = r.create_domain("Demo/內部", parent_id=self.pdid)
        self.assertEqual(r.project_domain_ids(), {self.pdid, sub})
        r.close()

    def test_no_bases_costs_one_query(self):
        """⚠️ 這條線每一次領域視野都會走——沒有專案時要**一個查詢結束**。"""
        r = Repository(temp_db())
        self.assertEqual(r.project_domain_ids(), set())
        r.close()


class TestInteractionCannotSeeProjects(Base):
    """站在**根**（＝整個思考模式）時，四種知識與子領域都看不到專案的。"""

    def test_every_kind_is_filtered(self):
        r = self.repo()
        v = r.domain_view(None)
        r.close()
        labels = {i["label"] for i in v["items"]}
        for gone in ("借來的判準", "專案的應用的對話", "專案的應用"):
            self.assertNotIn(gone, labels, f"專案的東西漏進思考模式：{gone}")
        for kept in ("我自己的判準", "我的應用的對話", "我的應用"):
            self.assertIn(kept, labels)

    def test_the_project_domain_is_not_listed_as_a_domain(self):
        """⚠️ 「領域」那一格列出專案、而它底下的東西在別格看不到 ⇒ 數字對不起來。"""
        r = self.repo()
        names = {c["name"] for c in r.domain_view(None)["children"]}
        r.close()
        self.assertIn("我的領域", names)
        self.assertNotIn("Demo", names)

    def test_library_page_too(self):
        d = self.c.get("/api/library").json()
        self.assertEqual([s["url"] for s in d["sources"]], ["https://example.com/mine"])
        self.assertEqual(d["n_projects"], 1)


class TestEveryEntryPointAsksTheLine(Base):
    """⚠️ 2026-08-30：「我剛剛新增了一個專案，發現來源竟然跑到思考模式那邊去了」。

    後端那條線是對的（`domain_view` 濾了、來源頁濾了），**漏的是兩個不經過
    `domain_view` 的入口**：`/api/domains`（餵領域選單與領域管理頁）與
    `/api/knowledge/inventory`（整理台）。專案的領域出現在選單裡
    ⇒ **你一站進去，它的幾百筆來源就全出來了**。

    ⇒ 判準要收緊一格：不是「每一格都問那條線」，是
    **「每一個回傳領域或知識清單的端點都要問」**——`domain_view` 不是唯一出口。
    """

    def test_the_domain_list_that_feeds_the_selector(self):
        """⚠️ 側欄根層的數字是對的，所以它看起來沒事——直到你從選單走進去。"""
        names = {d["name"] for d in self.c.get("/api/domains").json()["domains"]}
        self.assertIn("我的領域", names)
        self.assertNotIn("Demo", names, "專案的領域出現在思考模式的領域選單裡")

    def test_the_inventory_that_feeds_the_organiser(self):
        items = self.c.get("/api/knowledge/inventory").json()["items"]
        labels = {i["label"] for i in items}
        self.assertIn("我自己的判準", labels)
        for gone in ("借來的判準", "專案的應用"):
            self.assertNotIn(gone, labels, f"專案的東西漏進整理台：{gone}")

    def test_the_default_stays_unfiltered(self):
        """⚠️ `list_domains` 預設**必須**是 True——`project_domain_ids()`

        自己要用它建樹，預設 False 會**無限遞迴**（而那會是啟動就爆，不是靜默）。
        """
        r = self.repo()
        self.assertIn("Demo", {d["name"] for d in r.list_domains()})
        self.assertEqual(sorted(r.project_domain_ids()), [self.pdid])
        r.close()

    def test_a_new_endpoint_cannot_forget(self):
        """掃描層：任何端點呼叫這兩支而**沒有寫 `projects=`**，就是下一個漏的入口。

        ⓘ 這條守的是**未來新增的端點**——上面那幾條行為測試只認得我列出的那幾支。
        """
        import inspect
        import re

        from knowfield.web import app as mod
        # ⚠️ 先剝掉 docstring 與註解——不然掃到的是**說明文字裡的名字**，
        #    那會是一條假紅（而假紅會讓人開始無視這條測試）。
        src = re.sub(r'#.*$', '', re.sub(r'"""[\s\S]*?"""', '',
                                         inspect.getsource(mod)), flags=re.M)
        for name in ("list_domains", "_inventory_rows"):
            for m in re.finditer(rf"\.{name}\(([^)]*)\)", src):
                self.assertIn("projects=", m.group(1),
                              f"有端點呼叫 {name}() 卻沒說要不要專案：{m.group(0)}")


class TestDevModeSeesItsWholeProject(Base):
    """⚠️ 反過來也要成立：**站在專案裡就要看得到它的四種知識**。

    只做「互動看不到」而沒做「開發看得到」的話，那些東西就**兩邊都不見**了。
    """

    def test_standing_in_the_project_shows_all_four_kinds(self):
        r = self.repo()
        v = r.domain_view(self.pdid)
        r.close()
        kinds = {i["kind"] for i in v["items"]}
        self.assertEqual(kinds, {"source", "why_node", "conversation", "article"})
        labels = {i["label"] for i in v["items"]}
        self.assertIn("借來的判準", labels)
        self.assertNotIn("我自己的判準", labels)     # 你自己的也不會混進來

    def test_the_tree_endpoint_hands_over_that_domain(self):
        """側欄要拿這個 id 去問同一支 `domainView` ⇒ 它一定要給得出來。"""
        self.assertEqual(self.c.get(f"/api/bases/{self.bid}/tree").json()["domain_id"],
                         self.pdid)


class TestIsolation(Base):
    def test_another_owner_sees_no_project_domains(self):
        other = Repository(self.db, owner=999)
        self.assertEqual(other.project_domain_ids(), set())
        other.close()
