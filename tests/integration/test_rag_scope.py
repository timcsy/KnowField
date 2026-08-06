"""T018 [US2]：--today 只含最近一份匯整；預設涵蓋全部累積。"""

import unittest

from knowfield.rag.answerer import StubAnswerer
from knowfield.rag.service import RagService
from knowfield.rag.types import Scope
from knowfield.ranking.embeddings import HashingEmbedder
from knowfield.store.repository import Repository
from tests.rag_helpers import make_entry, seed_digest


class TestRagScope(unittest.TestCase):
    def test_today_vs_accumulated(self):
        repo = Repository(":memory:")
        seed_digest(repo, "2026-07-22", [
            make_entry(1, "Old", "https://a/old", "Agent memory", "agent memory old")])
        seed_digest(repo, "2026-07-23", [
            make_entry(1, "New", "https://a/new", "Agent memory", "agent memory new")])
        svc = RagService(repo, HashingEmbedder(), StubAnswerer(),
                         top_k=10, min_score=0.0)

        acc = {s.url for s in svc.answer("agent memory").sources}
        today = {s.url for s in svc.answer("agent memory", Scope(today=True)).sources}

        self.assertEqual(acc, {"https://a/old", "https://a/new"})   # 累積含兩份
        self.assertEqual(today, {"https://a/new"})                  # 今天只最近一份
        repo.close()


if __name__ == "__main__":
    unittest.main()
