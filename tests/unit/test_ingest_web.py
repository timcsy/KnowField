"""spec 030 web：貼上收進、PDF 收進（stub converter）、失敗 best-effort、純度守衛。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class StubConverter:
    def __init__(self, md="# 報告\n貓的內容。"):
        self.md = md

    def to_markdown(self, pdf_bytes=None, pdf_url=None):
        return self.md


class TestPasteIngest(unittest.TestCase):
    def test_paste_stores_chunks(self):
        db = temp_db()
        app = build_app(db)
        c = TestClient(app)
        long_text = "# 貓照顧\n" + ("貓要吃貓砂與貓糧。" * 60)
        r = c.post("/ingest/paste", data={"text": long_text, "title": "寵物筆記"},
                   follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("收進", r.text)
        self.assertGreater(len(Repository(db).list_corpus_entries()), 0)

    def test_paste_empty_no_store(self):
        db = temp_db()
        c = TestClient(build_app(db))
        c.post("/ingest/paste", data={"text": "   ", "title": ""}, follow_redirects=True)
        self.assertEqual(len(Repository(db).list_corpus_entries()), 0)


class TestPdfIngest(unittest.TestCase):
    def test_pdf_via_stub_converter(self):
        db = temp_db()
        app = build_app(db)
        app.state.doc_converter = StubConverter("# 貓報告\n貓的研究內容。")
        c = TestClient(app)
        r = c.post("/ingest/pdf", data={"url": "https://x/y.pdf", "title": "貓報告"},
                   follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(Repository(db).list_corpus_entries()), 0)

    def test_pdf_converter_failure_friendly(self):
        from learnnews.sources.base import SourceUnavailable

        class Boom:
            def to_markdown(self, pdf_bytes=None, pdf_url=None):
                raise SourceUnavailable("轉檔炸了")
        db = temp_db()
        app = build_app(db)
        app.state.doc_converter = Boom()
        r = TestClient(app).post("/ingest/pdf", data={"url": "https://x/y.pdf"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)                 # 不噴 500
        self.assertIn("失敗", r.text)
        self.assertEqual(len(Repository(db).list_corpus_entries()), 0)  # 半殘不寫


class TestUrlIngest(unittest.TestCase):
    _HTML = ("<html><head><title>貓文</title></head><body><article><h1>養貓</h1><p>"
             + "貓要吃貓糧與用貓砂很重要。" * 30 + "</p></article></body></html>")

    def test_url_ingest(self):
        db = temp_db()
        app = build_app(db)
        app.state.web_fetch = lambda u: self._HTML
        r = TestClient(app).post("/ingest/url", data={"url": "https://blog/x"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(Repository(db).list_corpus_entries()), 0)

    def test_url_fetch_failure_friendly(self):
        from learnnews.sources.base import SourceUnavailable

        def boom(u):
            raise SourceUnavailable("抓不到")
        db = temp_db()
        app = build_app(db)
        app.state.web_fetch = boom
        r = TestClient(app).post("/ingest/url", data={"url": "https://blog/x"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)                 # 不噴 500
        self.assertIn("失敗", r.text)
        self.assertEqual(len(Repository(db).list_corpus_entries()), 0)


class TestYoutubeIngest(unittest.TestCase):
    _WATCH = ('"title":"養貓指南""captionTracks":[{"baseUrl":"https://yt/api/timedtext?v=abc"}]')
    _CAP = '<transcript><text start="0" dur="2">貓要吃貓糧與用貓砂</text></transcript>'

    def test_youtube_ingest(self):
        db = temp_db()
        app = build_app(db)
        app.state.web_fetch = lambda u: (self._CAP if "timedtext" in u else self._WATCH)
        r = TestClient(app).post("/ingest/youtube", data={"url": "https://youtu.be/abcdefghij1"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(Repository(db).list_corpus_entries()), 0)

    def test_youtube_no_caption_friendly(self):
        db = temp_db()
        app = build_app(db)
        app.state.web_fetch = lambda u: "沒字幕頁"
        r = TestClient(app).post("/ingest/youtube", data={"url": "https://youtu.be/abcdefghij1"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)                 # 不噴 500
        self.assertIn("字幕", r.text)                        # 友善提示改用貼上
        self.assertEqual(len(Repository(db).list_corpus_entries()), 0)


class TestPurityGuard(unittest.TestCase):
    def test_ingested_not_in_field_prompt(self):
        db = temp_db()
        app = build_app(db)
        secret = "SECRET_外部觀點_不該進地基"
        TestClient(app).post("/ingest/paste", data={"text": secret, "title": "x"},
                             follow_redirects=True)
        from learnnews.chat.field_chat import build_field_system_prompt
        repo = Repository(db)
        roots = repo.list_why_nodes("anointed")
        n_anointed = len(roots)
        repo.close()
        self.assertNotIn(secret, build_field_system_prompt(roots))  # 收進不進地基
        self.assertEqual(n_anointed, 0)                            # 不自動變核心理解


if __name__ == "__main__":
    unittest.main()
