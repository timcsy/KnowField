"""spec 030：ContentIngestService——貼上/PDF→切塊→存成 corpus→可被 retrieve_corpus 檢索。

離線 stub embedder／stub converter，零外呼可測（教訓 1）。
"""

import unittest

from learnnews.ingest.service import ContentIngestService
from learnnews.rag.service import retrieve_corpus
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db


class StubEmbedder:
    """[1,0] 若含『貓』否則 [0,1]。"""
    def embed(self, text):
        return [1.0, 0.0] if "貓" in (text or "") else [0.0, 1.0]

    def embed_many(self, texts):
        return [self.embed(t) for t in texts]


class StubConverter:
    def __init__(self, md):
        self.md = md

    def to_markdown(self, pdf_bytes=None, pdf_url=None):
        return self.md


class TestIngestText(unittest.TestCase):
    def test_long_text_chunked_and_retrievable(self):
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder())
        long_text = "# 貓的照顧\n" + ("貓要吃貓砂與貓糧。" * 60) + "\n\n# 狗\n" + ("狗很忠誠。" * 60)
        res = svc.ingest_text(long_text, title="寵物筆記")
        self.assertEqual(res.status, "ingested")
        self.assertGreater(res.count, 1)                       # 切成多塊
        entries = repo.list_corpus_entries()
        self.assertEqual(len(entries), res.count)              # 每塊一筆 corpus
        hits = retrieve_corpus(repo, StubEmbedder(), "貓怎麼養", top_k=6, min_score=0.5)
        self.assertTrue(any("貓" in (h.body or "") for h in hits))  # 檢索得到含貓的塊
        repo.close()

    def test_title_from_article_heading(self):
        # 文章自己的 H1＝最貼近原標題，勝過 AI 摘要（且不叫 AI）
        class Boom:
            def reply(self, m):
                raise AssertionError("內容有標題不該叫 AI")
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder(), chat_backend=Boom())
        svc.ingest_text("# 深入解析Flow Matching技术\n\n這篇文章介紹貓…", title="")
        self.assertEqual(repo.list_source_groups()[0]["title"], "深入解析Flow Matching技术")
        repo.close()

    def test_ai_title_when_none(self):
        class TitleBackend:
            def reply(self, messages):
                return "貓咪照顧完全指南"
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder(), chat_backend=TitleBackend())
        svc.ingest_text("貓要吃貓糧與用貓砂，這是新手飼主的基本常識。", title="")  # 沒給標題
        self.assertEqual(repo.list_source_groups()[0]["title"], "貓咪照顧完全指南")  # AI 生
        repo.close()

    def test_ai_title_fallback_first_line(self):
        repo = Repository(temp_db())  # 無 chat_backend → 退回首行
        svc = ContentIngestService(repo, StubEmbedder())
        svc.ingest_text("首行當標題的貓內容\n第二段...", title="")
        self.assertEqual(repo.list_source_groups()[0]["title"], "首行當標題的貓內容")
        repo.close()

    def test_given_title_not_overridden(self):
        class Boom:
            def reply(self, m):
                raise AssertionError("有標題不該叫 AI")
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder(), chat_backend=Boom())
        svc.ingest_text("貓內容", title="我給的標題")
        self.assertEqual(repo.list_source_groups()[0]["title"], "我給的標題")
        repo.close()

    def test_source_url_recorded(self):
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder())
        svc.ingest_text("貓內容", title="貓", source_url="https://zhuanlan.zhihu.com/p/123")
        self.assertEqual(repo.list_source_groups()[0]["url"], "https://zhuanlan.zhihu.com/p/123")
        repo.close()

    def test_reason_and_date_recorded_and_editable(self):
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder())
        svc.ingest_text("貓內容", title="貓", note="為了養貓專案", ingested_at="2026-07")
        g = repo.list_source_groups()[0]
        self.assertEqual(g["note"], "為了養貓專案")
        self.assertEqual(g["ingested_at"], "2026-07")        # 大概日期（自由文字）
        repo.set_source_meta(g["url"], "改了原因", "2026-08-04")
        self.assertEqual(repo.source_meta(g["url"]),
                         {"note": "改了原因", "ingested_at": "2026-08-04"})  # 可編輯
        # 原因/日期不進 embedding 的正文
        self.assertNotIn("為了養貓專案", " ".join(e.body or "" for e in repo.list_corpus_entries()))
        repo.close()

    def test_empty_no_store(self):
        repo = Repository(temp_db())
        res = ContentIngestService(repo, StubEmbedder()).ingest_text("   ")
        self.assertEqual(res.status, "empty")
        self.assertEqual(len(repo.list_corpus_entries()), 0)
        repo.close()

    def test_duplicate_not_regrown(self):
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder())
        svc.ingest_text("貓要吃貓糧。", title="a")
        n1 = len(repo.list_corpus_entries())
        res2 = svc.ingest_text("貓要吃貓糧。", title="a")       # 同內容再收
        self.assertEqual(res2.status, "exists")                # 去重、不再增生
        self.assertEqual(len(repo.list_corpus_entries()), n1)
        repo.close()


class TestIngestUrl(unittest.TestCase):
    _HTML = ("<html><head><title>貓文</title></head><body><article>"
             "<h1>養貓指南</h1><p>" + "貓要吃貓糧與用貓砂。" * 40 + "</p></article></body></html>")

    def test_url_extracts_and_stores(self):
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder())
        res = svc.ingest_url("https://blog/x", http_get=lambda u: self._HTML)
        self.assertEqual(res.status, "ingested")
        self.assertTrue(any("貓" in (e.body or "") for e in repo.list_corpus_entries()))
        repo.close()

    def test_url_fetch_failure_raises(self):
        from learnnews.sources.base import SourceUnavailable

        def boom(u):
            raise SourceUnavailable("抓不到")
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder())
        with self.assertRaises(SourceUnavailable):
            svc.ingest_url("https://blog/x", http_get=boom)
        self.assertEqual(len(repo.list_corpus_entries()), 0)
        repo.close()


class TestIngestYoutube(unittest.TestCase):
    _WATCH = ('"title":"養貓指南"'
              '"captionTracks":[{"baseUrl":"https://yt/api/timedtext?v=abc"}]')
    _CAP = '<transcript><text start="0" dur="2">貓要吃貓糧與用貓砂很重要</text></transcript>'

    def _http(self, u):
        return self._CAP if "timedtext" in u else self._WATCH

    def test_youtube_transcript_stored(self):
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder())
        res = svc.ingest_youtube("https://youtu.be/abcdefghij1", http_get=self._http)
        self.assertEqual(res.status, "ingested")
        self.assertTrue(any("貓" in (e.body or "") for e in repo.list_corpus_entries()))
        repo.close()

    def test_no_captions_raises(self):
        from learnnews.sources.base import SourceUnavailable
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder())
        with self.assertRaises(SourceUnavailable):
            svc.ingest_youtube("https://youtu.be/abcdefghij1", http_get=lambda u: "沒字幕")
        repo.close()


class TestIngestPdf(unittest.TestCase):
    def test_pdf_via_stub_converter(self):
        repo = Repository(temp_db())
        md = "# 報告\n貓的研究內容很長。\n\n| 欄A | 欄B |\n| --- | --- |\n| 貓 | 1 |"
        svc = ContentIngestService(repo, StubEmbedder(), converter=StubConverter(md))
        res = svc.ingest_pdf(pdf_url="https://x/y.pdf", title="貓報告")
        self.assertEqual(res.status, "ingested")
        entries = repo.list_corpus_entries()
        self.assertTrue(any("| 欄A | 欄B |" in (e.body or "") for e in entries))  # 表格整塊
        repo.close()

    def test_converter_failure_raises(self):
        from learnnews.sources.base import SourceUnavailable

        class Boom:
            def to_markdown(self, pdf_bytes=None, pdf_url=None):
                raise SourceUnavailable("轉檔炸了")
        repo = Repository(temp_db())
        svc = ContentIngestService(repo, StubEmbedder(), converter=Boom())
        with self.assertRaises(SourceUnavailable):
            svc.ingest_pdf(pdf_url="https://x/y.pdf")
        self.assertEqual(len(repo.list_corpus_entries()), 0)   # 半殘不寫
        repo.close()


if __name__ == "__main__":
    unittest.main()
