"""T007 [US1]：arXiv id 正規化、id_list 解析、URL 淺抽、失敗。"""

import unittest

from learnnews.seed.fetch import fetch_arxiv_by_id, fetch_url, normalize_arxiv_id
from learnnews.sources.base import SourceUnavailable
from tests.seed_helpers import http_arxiv, http_fail, http_html


class TestNormalizeArxivId(unittest.TestCase):
    def test_various_forms(self):
        self.assertEqual(normalize_arxiv_id("1706.03762"), "1706.03762")
        self.assertEqual(normalize_arxiv_id("2407.12345v2"), "2407.12345")
        self.assertEqual(normalize_arxiv_id("arXiv:1706.03762"), "1706.03762")
        self.assertEqual(
            normalize_arxiv_id("https://arxiv.org/abs/1706.03762"), "1706.03762")

    def test_non_arxiv_is_none(self):
        self.assertIsNone(normalize_arxiv_id("https://example.com/blog/x"))
        self.assertIsNone(normalize_arxiv_id(""))


class TestFetch(unittest.TestCase):
    def test_arxiv_by_id(self):
        item = fetch_arxiv_by_id("1706.03762", http_get=http_arxiv)
        self.assertEqual(item.title, "Attention Is All You Need")
        self.assertEqual(item.url, "https://arxiv.org/abs/1706.03762")   # abs 裸 id url
        self.assertEqual(item.external_id, "1706.03762")
        self.assertIn("Transformer", item.abstract)

    def test_url_shallow_extract(self):
        get = http_html("Attention Explained", "Attention lets each token attend to all"
                        " other tokens, which is why transformers scale so well.")
        item = fetch_url("https://blog/x", http_get=get)
        self.assertEqual(item.title, "Attention Explained")
        self.assertIn("transformers scale", item.abstract)
        self.assertEqual(item.url, "https://blog/x")

    def test_url_no_body_fails(self):
        get = http_html("Empty", "short")     # 正文 < 30 字 → 取不到
        with self.assertRaises(SourceUnavailable):
            fetch_url("https://blog/empty", http_get=get)

    def test_fetch_failure_raises(self):
        with self.assertRaises(SourceUnavailable):
            fetch_arxiv_by_id("1706.03762", http_get=http_fail)


if __name__ == "__main__":
    unittest.main()
