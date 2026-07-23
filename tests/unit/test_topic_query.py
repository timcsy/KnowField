"""T003：主題查詢建構與來源可查詢性。"""

import unittest

from learnnews.models import Source
from learnnews.pull.topic_query import (
    arxiv_search_url,
    endpoint_for,
    is_queryable,
)


class TestTopicQuery(unittest.TestCase):
    def test_arxiv_search_url_encodes_topic(self):
        url = arxiv_search_url("latent reasoning", max_results=10)
        self.assertIn("search_query=", url)
        self.assertIn("all", url)
        self.assertIn("latent", url)
        self.assertIn("max_results=10", url)

    def test_is_queryable(self):
        arxiv = Source("a", "arXiv", "paper", "arxiv_api", "http://x")
        rss = Source("b", "Blog", "news", "rss", "http://feed")
        self.assertTrue(is_queryable(arxiv))
        self.assertFalse(is_queryable(rss))

    def test_endpoint_for_arxiv_uses_search(self):
        arxiv = Source("a", "arXiv", "paper", "arxiv_api", "http://orig")
        ep = endpoint_for(arxiv, "agent", 5)
        self.assertIn("search_query=", ep)
        self.assertNotEqual(ep, "http://orig")

    def test_endpoint_for_rss_keeps_original(self):
        rss = Source("b", "Blog", "news", "rss", "http://feed")
        self.assertEqual(endpoint_for(rss, "agent", 5), "http://feed")


if __name__ == "__main__":
    unittest.main()
