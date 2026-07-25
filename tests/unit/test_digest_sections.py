"""T003/T008：source_id round-trip、_section_of 分類、HN/Reddit 重分類。"""

import unittest

from learnnews.cli.fetchers import DEFAULT_SOURCES
from learnnews.models import Article, Digest, DigestEntry, Item
from learnnews.store.repository import Repository
from learnnews.web.app import _section_of
from tests.rag_helpers import temp_db


def _entry(title, url, sid):
    return DigestEntry(item=Item(source_id=sid, external_id="", title=title, url=url),
                       rank=1, relevance_score=0.9, matched_topic="",
                       article=Article(item_id=0, body="b", source_url=url, headline=title))


class TestDigestSections(unittest.TestCase):
    def test_source_id_round_trips(self):
        repo = Repository(temp_db())
        repo.save_digest(Digest(date="2026-07-26", entries=[
            _entry("論文", "https://a/1", "arxiv-cs"),
            _entry("新聞", "https://a/2", "techcrunch-ai")]))
        got = {e.item.title: e.item.source_id for e in repo.get_last_digest().entries}
        self.assertEqual(got["論文"], "arxiv-cs")
        self.assertEqual(got["新聞"], "techcrunch-ai")
        repo.close()

    def test_section_of(self):
        self.assertEqual(_section_of("paper"), "foundational")
        self.assertEqual(_section_of("blog"), "foundational")
        self.assertEqual(_section_of("news"), "news")
        self.assertEqual(_section_of(None), "news")            # 未知 → 新聞
        self.assertEqual(_section_of(""), "news")

    def test_hn_reddit_reclassified_news(self):
        by_id = {s.id: s for s in DEFAULT_SOURCES}
        self.assertEqual(by_id["hn-ai"].type, "news")          # 社群流 → 新聞
        self.assertEqual(by_id["reddit-localllama"].type, "news")
        # 基礎部落格仍是 blog（若在名冊）
        self.assertEqual(by_id["arxiv-cs"].type, "paper")


if __name__ == "__main__":
    unittest.main()
