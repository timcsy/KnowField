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
