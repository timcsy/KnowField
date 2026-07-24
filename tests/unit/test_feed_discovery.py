"""T004 [US1]：discover_feed／validate_feed／subscribe（可注入 http_get，離線）。"""

import unittest

from learnnews.sources.base import SourceUnavailable
from learnnews.sources.subscribe import discover_feed, subscribe, validate_feed

FEED = ('<?xml version="1.0"?><rss version="2.0"><channel><title>My Blog</title>'
        '<item><title>Post 1</title><link>https://blog/p1</link>'
        '<description>這是一篇夠長的貼文內容描述</description></item></channel></rss>')
HOMEPAGE = ('<html><head><title>My Blog</title>'
            '<link rel="alternate" type="application/rss+xml" href="/feed.xml">'
            '</head><body>hello</body></html>')
NO_FEED = '<html><head><title>Plain</title></head><body>沒有 feed 這裡什麼都沒有</body></html>'


def _http(homepage=HOMEPAGE, feed=FEED):
    """依 url 是否含 feed/rss 回 feed，否則回首頁。"""
    return lambda u: feed if ("feed" in u or "rss" in u) else homepage


class TestFeedDiscovery(unittest.TestCase):
    def test_url_is_feed(self):
        self.assertEqual(
            discover_feed("https://blog/feed.xml", _http()), "https://blog/feed.xml")

    def test_discover_from_homepage(self):
        self.assertEqual(
            discover_feed("https://blog/", _http()), "https://blog/feed.xml")

    def test_no_feed_returns_none(self):
        self.assertIsNone(discover_feed("https://x/", lambda u: NO_FEED))

    def test_validate_has_items(self):
        self.assertEqual(len(validate_feed("https://blog/feed.xml", _http())), 1)

    def test_subscribe_builds_source(self):
        s = subscribe("https://blog/", _http())
        self.assertEqual(s.access_method, "rss")
        self.assertEqual(s.endpoint, "https://blog/feed.xml")
        self.assertIn("My Blog", s.name)
        self.assertTrue(s.enabled)

    def test_subscribe_no_feed_raises(self):
        with self.assertRaises(SourceUnavailable):
            subscribe("https://x/", lambda u: NO_FEED)

    def test_subscribe_empty_feed_raises(self):
        empty = '<?xml version="1.0"?><rss version="2.0"><channel><title>X</title></channel></rss>'
        with self.assertRaises(SourceUnavailable):
            subscribe("https://blog/feed.xml", lambda u: empty)


if __name__ == "__main__":
    unittest.main()
