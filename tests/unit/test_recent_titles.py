"""T006 [US2]：recent_digest_titles 只取真實匯整標題、排除種子容器。"""

import unittest

from learnnews.config import SEEDS_DATE
from learnnews.models import Article, Digest, DigestEntry, Item
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db


def _entry(title, url):
    return DigestEntry(item=Item(source_id="s", external_id="", title=title, url=url),
                       rank=1, relevance_score=0.9, matched_topic="",
                       article=Article(item_id=0, body="b", source_url=url, headline=title))


class TestRecentTitles(unittest.TestCase):
    def test_excludes_seeds_and_takes_recent(self):
        repo = Repository(temp_db())
        repo.save_digest(Digest(date="2026-07-24", entries=[_entry("agent 記憶", "https://a/1")]))
        repo.save_digest(Digest(date="2026-07-25", entries=[_entry("latent reasoning", "https://a/2")]))
        # 種子容器（SEEDS_DATE）的標題不該進趨勢
        repo.save_digest(Digest(date=SEEDS_DATE, entries=[_entry("種子經典", "https://a/seed")]))

        titles = repo.recent_digest_titles(k=5)
        self.assertIn("agent 記憶", titles)
        self.assertIn("latent reasoning", titles)
        self.assertNotIn("種子經典", titles)                  # 種子排除
        repo.close()

    def test_empty_when_no_digest(self):
        repo = Repository(temp_db())
        self.assertEqual(repo.recent_digest_titles(), [])
        repo.close()


if __name__ == "__main__":
    unittest.main()
