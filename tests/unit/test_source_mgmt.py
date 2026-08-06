"""spec 031：來源管理（按 url 歸一列）、詳情拼回、rich-paste 圖片、LLM 清理。"""

import unittest

from fastapi.testclient import TestClient

from knowfield.ingest.clean import clean_markdown
from knowfield.ingest.service import ContentIngestService
from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db
from tests.web_helpers import build_app
from tests.web_helpers import temp_db as web_temp_db


class StubEmbedder:
    def embed(self, text):
        return [1.0, 0.0] if "貓" in (text or "") else [0.0, 1.0]

    def embed_many(self, texts):
        return [self.embed(t) for t in texts]


class TestSourceGrouping(unittest.TestCase):
    def test_group_delete_reclassify(self):
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder())
        svc.ingest_text("# 貓\n" + ("貓要吃貓糧與用貓砂。" * 60), title="養貓")  # 多塊
        groups = repo.list_source_groups()
        self.assertEqual(len(groups), 1)                 # 一來源一列（非 N 列）
        g = groups[0]
        self.assertGreater(g["count"], 1)                # 顯示塊數
        self.assertEqual(g["title"], "養貓")
        repo.set_source_class_by_url(g["url"], "explainer")
        self.assertEqual(repo.list_source_groups()[0]["source_class"], "explainer")  # 整篇標
        n = repo.delete_source(g["url"])
        self.assertEqual(n, g["count"])                  # 整份刪
        self.assertEqual(len(repo.list_source_groups()), 0)
        repo.close()

    def test_detail_stitch(self):
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder())
        body = "".join(f"第{i}句不同的貓內容。" for i in range(80))
        svc.ingest_text(body, title="長文")
        chunks = repo.get_source_chunks(repo.list_source_groups()[0]["url"])
        from knowfield.ingest.chunk import stitch_chunks
        stitched = stitch_chunks(chunks)
        self.assertIn("第0句", stitched)
        self.assertIn("第79句", stitched)
        self.assertEqual(stitched.count("第40句不同的貓內容"), 1)  # 去重疊：中段不重複
        repo.close()


class TestRichPaste(unittest.TestCase):
    _HTML = ('<html><body><nav>首頁 關於</nav><article><h1>圖文文章</h1>'
             '<p>' + "貓的內容很長要記得。" * 30 + '</p>'
             '<img src="https://pic.example/cat.jpg" alt="貓"></article>'
             '<footer>版權所有</footer></body></html>')

    def test_paste_html_strips_noise_keeps_image(self):
        db = web_temp_db()
        app = build_app(db)
        TestClient(app).post("/ingest/paste", data={"html": self._HTML, "text": ""},
                             follow_redirects=True)
        bodies = " ".join(e.body or "" for e in Repository(db).list_corpus_entries())
        self.assertIn("![貓](https://pic.example/cat.jpg)", bodies)   # 圖片行內
        self.assertNotIn("首頁 關於", bodies)                        # nav 剝掉
        self.assertNotIn("版權所有", bodies)                         # footer 剝掉

    def test_plain_text_still_works(self):
        db = web_temp_db()
        app = build_app(db)
        TestClient(app).post("/ingest/paste", data={"text": "純文字貓咪筆記", "html": ""},
                             follow_redirects=True)
        self.assertGreater(len(Repository(db).list_corpus_entries()), 0)


class TestLibraryWeb(unittest.TestCase):
    def test_library_one_row_and_detail(self):
        db = web_temp_db()
        app = build_app(db)
        c = TestClient(app)
        c.post("/ingest/paste", data={"text": "# 貓\n" + ("貓要吃貓糧。" * 60), "title": "養貓筆記"},
               follow_redirects=True)
        lib = c.get("/library")
        self.assertIn("養貓筆記", lib.text)
        self.assertIn("塊", lib.text)                    # 顯示塊數、非 N 列
        repo = Repository(db)
        url = repo.list_source_groups()[0]["url"]
        repo.close()
        detail = c.get("/source", params={"u": url})
        self.assertEqual(detail.status_code, 200)
        self.assertIn("貓要吃貓糧", detail.text)          # 原文可看

    def test_remove_by_url(self):
        db = web_temp_db()
        app = build_app(db)
        c = TestClient(app)
        c.post("/ingest/paste", data={"text": "貓" * 500, "title": "x"}, follow_redirects=True)
        repo = Repository(db)
        url = repo.list_source_groups()[0]["url"]
        repo.close()
        c.post("/library/remove", data={"url": url}, follow_redirects=True)
        self.assertEqual(len(Repository(db).list_source_groups()), 0)


class TestClean(unittest.TestCase):
    def test_clean_uses_backend(self):
        class Stub:
            def reply(self, messages):
                return "乾淨正文"
        self.assertEqual(clean_markdown("夾雜雜訊的內容", Stub()), "乾淨正文")

    def test_clean_failure_returns_original(self):
        class Boom:
            def reply(self, messages):
                raise RuntimeError("炸")
        self.assertEqual(clean_markdown("原文", Boom()), "原文")
        self.assertEqual(clean_markdown("原文", None), "原文")


if __name__ == "__main__":
    unittest.main()
