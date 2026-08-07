"""論文來源加料（arXiv）：抓乾淨 metadata（Abstract/作者/日期）＋PDF 存 /media，供論文展示。離線注入、零外呼。"""
import tempfile
import unittest
from pathlib import Path

from knowfield.ingest.media import load_paper_meta, source_pdf_name
from knowfield.ingest.paper import arxiv_id, enrich_arxiv, fetch_arxiv_meta, parse_arxiv_atom

_ATOM = """<feed><title>ArXiv Query</title><entry>
<title>Attention Is All You Need</title>
<summary>The dominant sequence transduction models are based on complex recurrent networks.</summary>
<author><name>Ashish Vaswani</name></author>
<author><name>Noam Shazeer</name></author>
<published>2017-06-12T17:57:34Z</published>
</entry></feed>"""


class TestPaper(unittest.TestCase):
    def test_arxiv_id_extract(self):
        self.assertEqual(arxiv_id("https://arxiv.org/abs/1706.03762"), "1706.03762")
        self.assertEqual(arxiv_id("https://arxiv.org/pdf/1706.03762v7"), "1706.03762")
        self.assertEqual(arxiv_id("https://blog.x/post"), "")

    def test_parse_atom(self):
        m = parse_arxiv_atom(_ATOM)
        self.assertEqual(m["title"], "Attention Is All You Need")     # 取 entry 的 title（非 feed）
        self.assertEqual(m["authors"], ["Ashish Vaswani", "Noam Shazeer"])
        self.assertEqual(m["published"], "2017-06-12")
        self.assertIn("dominant sequence", m["abstract"])

    def test_parse_missing_returns_none(self):
        self.assertIsNone(parse_arxiv_atom("<feed><title>只有 feed</title></feed>"))

    def test_fetch_meta_with_stub(self):
        m = fetch_arxiv_meta("1706.03762", http_get=lambda u: _ATOM)
        self.assertEqual(m["title"], "Attention Is All You Need")

    def test_enrich_saves_meta_and_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            url = "https://arxiv.org/abs/1706.03762"
            enrich_arxiv(d, url, http_get=lambda u: _ATOM, fetch_pdf_bytes=lambda u: b"%PDF fake")
            self.assertEqual(load_paper_meta(d, url)["title"], "Attention Is All You Need")
            self.assertTrue((Path(d) / source_pdf_name(url)).exists())     # PDF 也存了

    def test_enrich_non_arxiv_noop(self):
        with tempfile.TemporaryDirectory() as d:
            enrich_arxiv(d, "https://blog.x/post", http_get=lambda u: _ATOM, fetch_pdf_bytes=lambda u: b"x")
            self.assertIsNone(load_paper_meta(d, "https://blog.x/post"))    # 非 arXiv→不加料


if __name__ == "__main__":
    unittest.main()
