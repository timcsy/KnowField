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
