"""spec 029：檢索純函式 retrieve_corpus——找相關收進條目（離線、注入 stub embedder）。"""

import unittest

from learnnews.rag.service import retrieve_corpus
from learnnews.store.repository import Repository
from tests.rag_helpers import make_entry, seed_digest, temp_db


class StubEmbedder:
    """[1,0] 若含『貓』否則 [0,1]——讓 cosine 可控。"""
    def embed(self, text):
        return [1.0, 0.0] if "貓" in (text or "") else [0.0, 1.0]

    def embed_many(self, texts):
        return [self.embed(t) for t in texts]


def _repo_with(specs):
    repo = Repository(temp_db())
    entries = [make_entry(i + 1, t, u, "", b) for i, (t, u, b) in enumerate(specs)]
    seed_digest(repo, "2026-08-04", entries)
    return repo


class TestRetrieveCorpus(unittest.TestCase):
    def test_relevant_only(self):                       # T001 只回相關（門檻過濾）
        repo = _repo_with([("貓的文章", "https://a/1", "貓很可愛"),
                           ("狗的文章", "https://a/2", "狗很忠誠"),
                           ("貓咪飼養", "https://a/3", "貓需要貓砂")])
        hits = retrieve_corpus(repo, StubEmbedder(), "貓怎麼養", top_k=6, min_score=0.5)
        titles = [h.title for h in hits]
        self.assertIn("貓的文章", titles)
        self.assertIn("貓咪飼養", titles)
        self.assertNotIn("狗的文章", titles)            # cosine 0 < 0.5
        repo.close()

    def test_empty_corpus(self):                        # T001 空語料→[]
        repo = Repository(temp_db())
        self.assertEqual(retrieve_corpus(repo, StubEmbedder(), "貓", top_k=6, min_score=0.5), [])
        repo.close()

    def test_none_relevant(self):                       # T001 全不相關→[]
        repo = _repo_with([("狗的文章", "https://a/2", "狗很忠誠")])
        self.assertEqual(retrieve_corpus(repo, StubEmbedder(), "貓", top_k=6, min_score=0.5), [])
        repo.close()

    def test_top_k(self):                               # T001 截斷
        repo = _repo_with([("貓1", "u1", "貓"), ("貓2", "u2", "貓"), ("貓3", "u3", "貓")])
        self.assertEqual(len(retrieve_corpus(repo, StubEmbedder(), "貓", top_k=2, min_score=0.5)), 2)
        repo.close()


if __name__ == "__main__":
    unittest.main()
