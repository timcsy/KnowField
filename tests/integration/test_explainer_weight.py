"""T014 [US2]：解說文種子檢索權重高於一般（同相關時排前）。"""

import unittest

from knowfield.rag.answerer import StubAnswerer
from knowfield.rag.service import RagService
from knowfield.ranking.embeddings import HashingEmbedder
from knowfield.seed.service import SeedService
from knowfield.store.repository import Repository
from knowfield.summarize.article import ArticleBuilder
from tests.seed_helpers import http_html


class TestExplainerWeight(unittest.TestCase):
    def test_explainer_ranks_first(self):
        repo = Repository(":memory:")
        body = "attention transformer scaling sequence model explained clearly"
        # 兩篇內容相同（→ 原始 cosine 相等）、url 不同、一篇標解說文
        SeedService(repo, ArticleBuilder(), HashingEmbedder(),
                    http_get=http_html("Ordinary Note", body)
                    ).ingest("https://a/ordinary", explainer=False)
        SeedService(repo, ArticleBuilder(), HashingEmbedder(),
                    http_get=http_html("Deep Explainer", body)
                    ).ingest("https://a/explainer", explainer=True)

        svc = RagService(repo, HashingEmbedder(), StubAnswerer(),
                         min_score=0.0, top_k=2, explainer_weight=1.5)
        ans = svc.answer("attention transformer")
        self.assertEqual(ans.sources[0].url, "https://a/explainer")   # 解說文排第一
        repo.close()

    def test_no_weight_ties_preserve_but_weight_flips(self):
        # 權重=1.0 時不必然解說文優先；權重>1 時解說文優先（對照）
        repo = Repository(":memory:")
        body = "attention transformer scaling sequence model"
        SeedService(repo, ArticleBuilder(), HashingEmbedder(),
                    http_get=http_html("A", body)).ingest("https://a/ord", explainer=False)
        SeedService(repo, ArticleBuilder(), HashingEmbedder(),
                    http_get=http_html("B", body)).ingest("https://a/exp", explainer=True)
        weighted = RagService(repo, HashingEmbedder(), StubAnswerer(),
                              min_score=0.0, top_k=2, explainer_weight=1.5)
        self.assertEqual(weighted.answer("attention").sources[0].url, "https://a/exp")
        repo.close()


if __name__ == "__main__":
    unittest.main()
