"""T014 [US1]：entry_embeddings 存取、惰性回填、批次、tag 不符重嵌。"""

import unittest

from learnnews.ranking.embeddings import HashingEmbedder
from learnnews.store.repository import Repository
from tests.rag_helpers import make_entry, seed_digest


class SpyEmbedder:
    """包 HashingEmbedder，數 embed_many 呼叫次數。"""

    def __init__(self) -> None:
        self.inner = HashingEmbedder()
        self.dim = self.inner.dim
        self.many_calls = 0

    def embed(self, text):
        return self.inner.embed(text)

    def embed_many(self, texts):
        self.many_calls += 1
        return self.inner.embed_many(texts)


class TestEntryEmbeddings(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")
        seed_digest(self.repo, "2026-07-23", [
            make_entry(1, "A", "https://a/1", "Agent memory", "agent memory systems"),
            make_entry(2, "B", "https://a/2", "Compiler", "compiler register loop"),
        ])
        self.entries = self.repo.list_corpus_entries()

    def test_save_get_roundtrip(self):
        eid = self.entries[0].entry_id
        self.repo.save_entry_embedding(eid, "hashing-256", [0.1, 0.2, 0.3])
        self.assertEqual(self.repo.get_entry_embedding(eid, "hashing-256"), [0.1, 0.2, 0.3])
        self.assertIsNone(self.repo.get_entry_embedding(eid, "other-tag"))

    def test_ensure_batches_then_caches(self):
        spy = SpyEmbedder()
        vecs = self.repo.ensure_embeddings(self.entries, spy, "hashing-256")
        self.assertEqual(len(vecs), 2)
        self.assertEqual(spy.many_calls, 1)          # 一次批次，非逐一
        spy2 = SpyEmbedder()
        self.repo.ensure_embeddings(self.entries, spy2, "hashing-256")
        self.assertEqual(spy2.many_calls, 0)         # 已落庫 → 不重算

    def test_tag_mismatch_recomputes(self):
        self.repo.ensure_embeddings(self.entries, HashingEmbedder(), "hashing-256")
        spy = SpyEmbedder()
        self.repo.ensure_embeddings(self.entries, spy, "openai-x")  # 換 tag
        self.assertEqual(spy.many_calls, 1)          # 不同空間需重嵌

    def tearDown(self):
        self.repo.close()


if __name__ == "__main__":
    unittest.main()
