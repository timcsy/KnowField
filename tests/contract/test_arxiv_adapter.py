"""T014：ArxivAdapter 契約——解析樣本、每則有原文連結、失敗明拋。"""

import unittest
from datetime import datetime

from learnnews.sources.arxiv import ArxivAdapter
from learnnews.sources.base import SourceUnavailable

_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Efficient LLM Inference</title>
    <summary>We study inference optimization.</summary>
    <published>2026-07-20T00:00:00Z</published>
    <link rel="alternate" href="http://arxiv.org/abs/2401.00001v1"/>
  </entry>
</feed>"""


class TestArxivAdapter(unittest.TestCase):
    def test_parses_entry(self):
        a = ArxivAdapter("arxiv", lambda since: _SAMPLE)
        items = a.fetch(datetime(2026, 7, 1))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Efficient LLM Inference")
        self.assertTrue(items[0].has_source_link())
        self.assertTrue(items[0].content_hash)

    def test_bad_xml_raises_unavailable(self):
        a = ArxivAdapter("arxiv", lambda since: "<not-xml")
        with self.assertRaises(SourceUnavailable):
            a.fetch(datetime(2026, 7, 1))


if __name__ == "__main__":
    unittest.main()
