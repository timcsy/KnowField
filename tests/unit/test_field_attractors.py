"""T003：list_field_attractors 只含種子＋已冊封根因（不含每日流、不含候選根因）。"""

import unittest

from learnnews.models import Article, Digest, DigestEntry, Item
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db


def _seed_entry(title, url):
    return DigestEntry(item=Item(source_id="s", external_id="", title=title, url=url),
                       rank=1, relevance_score=0.9, matched_topic="",
                       article=Article(item_id=0, body="b", source_url=url, headline=title))


class TestFieldAttractors(unittest.TestCase):
    def test_only_seeds_and_anointed_roots(self):
        repo = Repository(temp_db())
        # 每日流（不該進吸引子）
        repo.save_digest(Digest(date="2026-07-26", entries=[_seed_entry("今日新聞", "https://a/news")]))
        # 種子
        repo.ingest_seed(Item(source_id="s", external_id="", title="種子文", url="https://a/seed"),
                         Article(item_id=0, body="種子內容", source_url="https://a/seed", headline="種子文"))
        # 根因：一冊封、一候選
        a = repo.add_why_node("已冊封根因", ["https://a/r"], [], False, 1, "2026-07-26")
        repo.anoint_why_node(a)
        repo.add_why_node("候選根因", ["https://a/c"], [], False, 2, "2026-07-26")

        atts = repo.list_field_attractors()
        bodies = [x.body for x in atts]
        titles = [x.title for x in atts]
        self.assertTrue(any("種子內容" in b for b in bodies))       # 種子在
        self.assertTrue(any("已冊封根因" in b for b in bodies))      # 已冊封根因在
        self.assertNotIn("今日新聞", titles)                         # 每日流不在
        self.assertFalse(any("候選根因" in b for b in bodies))       # 候選（未冊封）不在
        repo.close()


if __name__ == "__main__":
    unittest.main()
