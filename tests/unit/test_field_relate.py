"""T005-T007 [US1/2/3]：FieldRelate——近→判關係、遠→成核、場空→提示、排除自己、不改場。"""

import unittest

from learnnews.field.relate import FieldRelate, StubRelationJudge
from learnnews.ranking.embeddings import HashingEmbedder
from learnnews.models import Article, Item
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db


class _KwEmbedder:
    """含 MATCH → [1,0]，否則 [0,1]；令材料與含 MATCH 的吸引子相近。"""
    dim = 2
    def embed(self, text):
        return [1.0, 0.0] if "MATCH" in (text or "") else [0.0, 1.0]
    def embed_many(self, texts):
        return [self.embed(t) for t in texts]


def _seed(repo, title, body, url):
    repo.ingest_seed(Item(source_id="s", external_id="", title=title, url=url),
                     Article(item_id=0, body=body, source_url=url, headline=title))


class TestFieldRelate(unittest.TestCase):
    def _fr(self, repo, embedder=None, min_score=0.5):
        return FieldRelate(embedder or _KwEmbedder(), StubRelationJudge(), repo, min_score)

    def test_near_attractor_judges_relation(self):
        repo = Repository(temp_db())
        _seed(repo, "MATCH 種子", "MATCH 這是相關吸引子", "https://a/1")
        out = self._fr(repo).relate("MATCH 材料", "MATCH 內文")
        self.assertIn(out.kind, ("extend", "contradict", "none"))   # 來自 judge
        self.assertIsNotNone(out.attractor)
        # 不改場
        self.assertEqual(len(repo.list_seeds()), 1)
        repo.close()

    def test_far_from_all_nucleate(self):
        repo = Repository(temp_db())
        _seed(repo, "種子", "與材料無關的吸引子", "https://a/1")   # 無 MATCH → cosine 低
        out = self._fr(repo).relate(
            "MATCH 全新方向",
            "MATCH 這是一段夠長、夠實質的材料內文，遠離場裡所有既有吸引子，是新地基的訊號。")
        self.assertEqual(out.kind, "nucleate")                # 離所有吸引子都遠 → 成核候選
        repo.close()

    def test_empty_field(self):
        repo = Repository(temp_db())
        out = self._fr(repo).relate("材料", "內文")
        self.assertEqual(out.kind, "empty")                   # 場空
        repo.close()

    def test_excludes_self(self):
        repo = Repository(temp_db())
        _seed(repo, "MATCH 這篇本身", "MATCH 內文", "https://a/self")
        # 材料 url＝該種子 → 排除自己 → 場只剩它、排除後無吸引子 → empty/nucleate（非配對自己）
        out = self._fr(repo).relate("MATCH 這篇本身", "MATCH 內文", exclude_url="https://a/self")
        self.assertIsNone(out.attractor)                      # 沒把自己當吸引子
        repo.close()


if __name__ == "__main__":
    unittest.main()
