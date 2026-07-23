"""T017：RssAdapter 契約（RSS 2.0 與 Atom／email-ingestion）。"""

import unittest
from datetime import datetime

from learnnews.sources.rss import RssAdapter
from learnnews.sources.base import SourceUnavailable

_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>某 AI 部落格</title>
  <item>
    <title>新模型發表</title>
    <link>https://blog.example.com/post1</link>
    <description>簡介。</description>
    <guid>post1</guid>
    <pubDate>Mon, 21 Jul 2026 10:00:00 GMT</pubDate>
  </item>
</channel></rss>"""

_ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>tag:news,1</id>
    <title>電子報條目</title>
    <summary>內容。</summary>
    <link rel="alternate" href="https://news.example.com/a"/>
    <updated>2026-07-21T10:00:00Z</updated>
  </entry>
</feed>"""


class TestRssAdapter(unittest.TestCase):
    def test_rss(self):
        a = RssAdapter("blog", lambda since: _RSS)
        items = a.fetch(datetime(2026, 7, 1))
        self.assertEqual(items[0].title, "新模型發表")
        self.assertEqual(items[0].url, "https://blog.example.com/post1")

    def test_atom_email_ingest(self):
        a = RssAdapter("newsletter", lambda since: _ATOM)
        items = a.fetch(datetime(2026, 7, 1))
        self.assertEqual(items[0].url, "https://news.example.com/a")
        self.assertTrue(items[0].has_source_link())

    def test_bad_raises(self):
        a = RssAdapter("blog", lambda since: "<broken")
        with self.assertRaises(SourceUnavailable):
            a.fetch(datetime(2026, 7, 1))


if __name__ == "__main__":
    unittest.main()
