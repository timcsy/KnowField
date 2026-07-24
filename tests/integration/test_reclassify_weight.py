"""T010 [US2]：重分類為解說文 → ask 檢索權重提高。"""

import unittest

from learnnews.models import Article, Item
from learnnews.rag.answerer import StubAnswerer
from learnnews.rag.service import RagService, embedder_tag
from learnnews.rag.types import CorpusEntry
from learnnews.ranking.embeddings import HashingEmbedder
from learnnews.store.repository import Repository


def _add_seed(repo, title, url, body, cls="ordinary"):
    item = Item(source_id="seed", external_id="", title=title, url=url)
    eid = repo.ingest_seed(item, Article(item_id=0, body=body, source_url=url,
                                         headline=title), cls)
    emb = HashingEmbedder()
    repo.ensure_embeddings(
        [CorpusEntry(entry_id=eid, title=title, url=url, headline=title, body=body,
                     source_class=cls)], emb, embedder_tag(emb))
    return eid


class TestReclassifyWeight(unittest.TestCase):
    def test_reclassify_to_explainer_raises_rank(self):
        repo = Repository(":memory:")
        body = "attention transformer scaling sequence model"
        _add_seed(repo, "A", "https://a/ordinary", body, "ordinary")
        b = _add_seed(repo, "B", "https://a/target", body, "ordinary")   # 同內容
        svc = RagService(repo, HashingEmbedder(), StubAnswerer(),
                         min_score=0.0, top_k=2, explainer_weight=1.5)

        repo.set_seed_class(b, "explainer")                              # 重分類 b
        ans = svc.answer("attention transformer")
        self.assertEqual(ans.sources[0].url, "https://a/target")        # b 因權重排第一
        repo.close()


if __name__ == "__main__":
    unittest.main()
