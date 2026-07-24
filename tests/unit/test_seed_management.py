"""T005 [US1/US3]：list_seeds 只列種子、delete_seed 連清嵌入＋拒每日流、set_seed_class。"""

import unittest

from learnnews.models import Article, Item
from learnnews.ranking.embeddings import HashingEmbedder
from learnnews.rag.service import embedder_tag
from learnnews.rag.types import CorpusEntry
from learnnews.store.repository import Repository
from tests.rag_helpers import make_entry, seed_digest


def _add_seed(repo, title, url, body, cls="ordinary"):
    item = Item(source_id="seed", external_id="", title=title, url=url)
    art = Article(item_id=0, body=body, source_url=url, headline=title)
    eid = repo.ingest_seed(item, art, cls)
    emb = HashingEmbedder()
    repo.ensure_embeddings(
        [CorpusEntry(entry_id=eid, title=title, url=url, headline=title, body=body,
                     source_class=cls)], emb, embedder_tag(emb))
    return eid


class TestSeedManagement(unittest.TestCase):
    def test_list_seeds_excludes_daily_flow(self):
        repo = Repository(":memory:")
        seed_digest(repo, "2026-07-23",
                    [make_entry(1, "Daily", "https://a/daily", "H", "b")])
        _add_seed(repo, "Seed A", "https://a/seed", "seed body")
        urls = {s.url for s in repo.list_seeds()}
        self.assertIn("https://a/seed", urls)
        self.assertNotIn("https://a/daily", urls)      # 每日流不列
        repo.close()

    def test_delete_seed_clears_embedding(self):
        repo = Repository(":memory:")
        eid = _add_seed(repo, "Seed", "https://a/1", "agent memory")
        self.assertIsNotNone(repo.get_entry_embedding(eid, "hashing-256"))
        self.assertTrue(repo.delete_seed(eid))
        self.assertEqual(repo.list_seeds(), [])
        self.assertIsNone(repo.get_entry_embedding(eid, "hashing-256"))   # 無孤兒
        repo.close()

    def test_delete_refuses_daily_flow(self):
        repo = Repository(":memory:")
        seed_digest(repo, "2026-07-23",
                    [make_entry(1, "Daily", "https://a/daily", "H", "b")])
        daily = repo.list_corpus_entries(today=True)[0]
        self.assertFalse(repo.delete_seed(daily.entry_id))               # 流不可刪
        self.assertEqual(len(repo.list_corpus_entries(today=True)), 1)   # 仍在
        repo.close()

    def test_set_seed_class(self):
        repo = Repository(":memory:")
        eid = _add_seed(repo, "Seed", "https://a/1", "body", cls="ordinary")
        self.assertTrue(repo.set_seed_class(eid, "explainer"))
        self.assertEqual(repo.list_seeds()[0].source_class, "explainer")
        self.assertFalse(repo.set_seed_class(eid, "bogus"))              # 非法值
        repo.close()

    def test_set_class_refuses_daily_flow(self):
        repo = Repository(":memory:")
        seed_digest(repo, "2026-07-23",
                    [make_entry(1, "Daily", "https://a/daily", "H", "b")])
        daily = repo.list_corpus_entries(today=True)[0]
        self.assertFalse(repo.set_seed_class(daily.entry_id, "explainer"))
        repo.close()


if __name__ == "__main__":
    unittest.main()
