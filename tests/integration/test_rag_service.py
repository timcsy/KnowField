"""T013 [US1]：RagService 檢索→合成→溯源；語義命中；來源由檢索集合生成。"""

import unittest

from learnnews.rag.answerer import StubAnswerer
from learnnews.rag.service import RagService
from learnnews.ranking.embeddings import HashingEmbedder
from learnnews.store.repository import Repository
from tests.rag_helpers import make_entry, seed_digest


def _svc(repo, **kw):
    return RagService(repo, HashingEmbedder(), StubAnswerer(), **kw)


class TestRagService(unittest.TestCase):
    def test_retrieval_cites_matching_source(self):
        repo = Repository(":memory:")
        seed_digest(repo, "2026-07-23", [
            make_entry(1, "Agent paper", "https://a/agent", "Agent memory",
                       "agent memory retrieval augmented systems"),
            make_entry(2, "Compiler paper", "https://a/comp", "Compiler",
                       "compiler register allocation loop unrolling"),
        ])
        ans = _svc(repo, top_k=1, min_score=0.0).answer("agent memory retrieval")
        self.assertFalse(ans.no_material)
        self.assertEqual(len(ans.sources), 1)
        self.assertEqual(ans.sources[0].url, "https://a/agent")   # 命中 agent 那則
        self.assertIn("[1]", ans.text)                            # 逐點標來源
        repo.close()

    def test_semantic_hit_different_wording(self):
        repo = Repository(":memory:")
        seed_digest(repo, "2026-07-23", [
            make_entry(1, "t", "https://a/1", "Agent memory systems",
                       "agent memory retrieval"),
        ])
        ans = _svc(repo, min_score=0.0).answer("memory agent")   # 詞序不同、語義相關
        self.assertFalse(ans.no_material)
        self.assertEqual(ans.sources[0].url, "https://a/1")
        repo.close()

    def test_sources_only_from_retrieved(self):
        # 溯源鐵律：sources 只含實際檢索到的條目（原則 3）
        repo = Repository(":memory:")
        seed_digest(repo, "2026-07-23", [
            make_entry(1, "Hit", "https://a/hit", "Agent memory", "agent memory"),
            make_entry(2, "Miss", "https://a/miss", "Cooking", "recipe kitchen food"),
        ])
        ans = _svc(repo, top_k=1, min_score=0.05).answer("agent memory")
        urls = {s.url for s in ans.sources}
        self.assertIn("https://a/hit", urls)
        self.assertNotIn("https://a/miss", urls)
        repo.close()


if __name__ == "__main__":
    unittest.main()
