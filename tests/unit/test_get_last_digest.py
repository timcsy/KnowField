"""T002：get_last_digest() 讀最近匯整全部 entries（含 headline、圖）。"""

import unittest

from learnnews.models import Article, Digest, DigestEntry, Figure, Item
from learnnews.store.repository import Repository


class TestGetLastDigest(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")

    def tearDown(self):
        self.repo.close()

    def test_none_when_empty(self):
        self.assertIsNone(self.repo.get_last_digest())

    def test_round_trip(self):
        art = Article(item_id=0, body="散文本體。", source_url="https://a/1",
                      headline="整理標題",
                      figure=Figure(kind="原文", url="https://img/x.jpg"))
        item = Item(source_id="s", external_id="1", title="原標題", url="https://a/1")
        self.repo.save_digest(Digest(date="2026-07-23", entries=[
            DigestEntry(item=item, rank=1, relevance_score=0.9, article=art,
                        matched_topic="agent")]))
        d = self.repo.get_last_digest()
        self.assertIsNotNone(d)
        self.assertEqual(d.date, "2026-07-23")
        e = d.entries[0]
        self.assertEqual(e.item.title, "原標題")
        self.assertEqual(e.article.headline, "整理標題")
        self.assertEqual(e.article.body, "散文本體。")
        self.assertEqual(e.article.figure.url, "https://img/x.jpg")

    def test_returns_latest(self):
        for dt in ("2026-07-21", "2026-07-22", "2026-07-23"):
            self.repo.save_digest(Digest(date=dt, entries=[]))
        self.assertEqual(self.repo.get_last_digest().date, "2026-07-23")


if __name__ == "__main__":
    unittest.main()
