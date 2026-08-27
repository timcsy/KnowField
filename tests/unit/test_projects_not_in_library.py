"""spec 080 收尾：專案的來源**不出現在互動的來源頁**（使用者 2026-08-27）。

⚠️ 使用者：「為何開發的來源都跑到互動模式那邊了？」
   ——正式庫 226 份專案檔 vs 他自己收的 9 份，一列一筆、新的在上
   ⇒ 他自己收的被壓到最底下。「專案就是來源」是對的，**但來源頁不是唯一的呈現**。

⚠️ 而它們**仍在語料裡、仍會被引用** ⇒ 少了它們的那一頁**要說出來**，
   否則就變成「看不到卻會影響回答」，那是這個庫記過的那種沉默。
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
    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)
        r = Repository(self.db)
        svc = ContentIngestService(r, _FakeEmb(), None)
        svc._ingest_markdown("我自己收的一段。", "我的來源", "https://example.com/mine")
        # ⚠️ 那條線是**領域**不是網址前綴——一份判準、一個地方（`project_domain_ids`）。
        #    所以測資也要照真實路徑來：base 記著它的領域，來源歸在那個領域底下。
        self.bid = r.add_ext_base("timcsy/Demo")
        self.did = r.create_domain("Demo")
        r.set_ext_domain(self.bid, self.did)
        for p in ("knowledge/experience.md", "knowledge/history/1-x.md"):
            url = f"github://timcsy/Demo/{p}"
            svc._ingest_markdown("專案的一段。", p.split("/")[-1], url)
            r.set_knowledge_domain("source", url, self.did, by="machine")
        r.close()


class TestLibraryHidesProjects(Base):
    def test_library_lists_only_your_own(self):
        d = self.c.get("/api/library").json()
        self.assertEqual([s["url"] for s in d["sources"]], ["https://example.com/mine"])

    def test_but_it_says_how_many_were_left_out(self):
        """⚠️ 不說的話，這一頁就是「看不到卻會影響回答」。"""
        self.assertEqual(self.c.get("/api/library").json()["n_projects"], 2)

    def test_they_are_still_in_the_corpus(self):
        """⚠️ 濾的是**這一頁**，不是語料——濾掉語料會推翻「跨專案是免費的」。"""
        r = Repository(self.db)
        urls = {e.url for e in r.list_corpus_entries()}
        r.close()
        self.assertIn("github://timcsy/Demo/knowledge/experience.md", urls)

    def test_provenance_still_sees_every_source(self):
        """⚠️ `why_node_source_provenance` 要的是**全部**來源——

        濾成預設值的話，由來會靜默斷線（根因指到一個「不存在」的來源）。
        """
        r = Repository(self.db)
        self.assertEqual(len(r.list_source_groups()), 3)
        self.assertEqual(len(r.list_source_groups(projects=False)), 1)
        r.close()


class TestCitationsNameTheirOwner(unittest.TestCase):
    """⚠️ 專案的檔標成「你收藏的」是**假話**——那是把別人的東西掛上你的名字。"""

    def _read(self, rel):
        import pathlib
        import re
        src = (pathlib.Path(__file__).resolve().parents[2] / "frontend/src" / rel
               ).read_text(encoding="utf-8")
        return re.sub(r"/\*[\s\S]*?\*/", "", re.sub(r"//.*$", "", src, flags=re.M))

    def test_project_citation_is_badged_with_the_repo(self):
        code = self._read("components/Sources.tsx")
        self.assertIn("projectOf", code)
        self.assertIn("📁 {repo}", code)

    def test_project_citation_does_not_link_to_a_broken_scheme(self):
        """⚠️ `github://…` 瀏覽器打不開 ⇒ 連站內的來源詳情頁（讀得到被引用的原文）。"""
        code = self._read("components/Sources.tsx")
        self.assertIn("/source?u=", code)

    def test_the_library_page_says_where_they_went(self):
        code = self._read("pages/SourcesPage.tsx")
        self.assertIn("n_projects", code)
        self.assertIn("到開發模式看", code)
