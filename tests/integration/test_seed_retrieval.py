"""T009 [US1]：種子進 KB → ask 檢索得到＋溯源；去重。"""

import unittest

from knowfield.rag.answerer import StubAnswerer
from knowfield.rag.service import RagService
from knowfield.ranking.embeddings import HashingEmbedder
from knowfield.seed.service import SeedService
from knowfield.store.repository import Repository
from knowfield.summarize.article import ArticleBuilder
from tests.seed_helpers import http_arxiv


def _seed_service(repo, http_get):
    return SeedService(repo, ArticleBuilder(), HashingEmbedder(), http_get=http_get)


class TestSeedRetrieval(unittest.TestCase):
    def test_ingested_seed_is_retrievable_and_sourced(self):
        repo = Repository(":memory:")
        res = _seed_service(repo, http_arxiv).ingest("1706.03762")
        self.assertEqual(res.status, "ingested")
        self.assertEqual(res.title, "Attention Is All You Need")

        svc = RagService(repo, HashingEmbedder(), StubAnswerer(), min_score=0.0)
        ans = svc.answer("attention transformer")
        self.assertFalse(ans.no_material)
        urls = {s.url for s in ans.sources}
        self.assertIn("https://arxiv.org/abs/1706.03762", urls)   # 種子被檢索到＋溯源
        repo.close()

    def test_duplicate_ingest_no_dup(self):
        repo = Repository(":memory:")
        svc = _seed_service(repo, http_arxiv)
        svc.ingest("1706.03762")
        res2 = svc.ingest("arXiv:1706.03762v5")                   # 同篇不同寫法
        self.assertEqual(res2.status, "exists")
        # 種子容器只有一份
        seeds = [e for e in repo.list_corpus_entries()
                 if e.url == "https://arxiv.org/abs/1706.03762"]
        self.assertEqual(len(seeds), 1)
        repo.close()

    def test_today_excludes_seeds(self):
        # 種子不屬於「今天這份匯整」（spec 006 R2）
        repo = Repository(":memory:")
        _seed_service(repo, http_arxiv).ingest("1706.03762")
        self.assertEqual(repo.list_corpus_entries(today=True), [])   # 無真實每日匯整
        self.assertEqual(len(repo.list_corpus_entries(today=False)), 1)  # 累積含種子
        repo.close()


if __name__ == "__main__":
    unittest.main()
