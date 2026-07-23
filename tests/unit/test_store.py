"""T005：store schema 與 repository round-trip。"""

import unittest

from learnnews.models import BehaviorSignal, InterestProfile, Item, Source
from learnnews.store.repository import Repository


class TestStore(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")

    def tearDown(self):
        self.repo.close()

    def test_source_round_trip(self):
        s = Source("arxiv", "arXiv", "paper", "arxiv_api", "http://x")
        self.repo.upsert_source(s)
        got = self.repo.list_sources()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].id, "arxiv")
        self.assertTrue(got[0].enabled)

    def test_source_enable_disable(self):
        self.repo.upsert_source(Source("a", "A", "paper", "arxiv_api", "http://x"))
        self.repo.set_source_enabled("a", False)
        self.assertEqual(self.repo.list_sources(enabled_only=True), [])

    def test_item_dedup_by_content_hash(self):
        it = Item(source_id="a", external_id="2401.1", title="T", url="http://u",
                  content_hash="h1")
        id1 = self.repo.add_item(it)
        dup = Item(source_id="b", external_id="2401.1", title="T", url="http://u",
                   content_hash="h1")
        id2 = self.repo.add_item(dup)
        self.assertEqual(id1, id2)  # 相同 content_hash 不重複插入

    def test_interest_profile_round_trip(self):
        p = InterestProfile(explicit_topics=["LLM 推理", "agent"],
                            learned_weights={"agent": 0.5})
        self.repo.save_interest_profile(p)
        got = self.repo.get_interest_profile()
        self.assertEqual(got.explicit_topics, ["LLM 推理", "agent"])
        self.assertEqual(got.learned_weights, {"agent": 0.5})

    def test_behavior_signal(self):
        self.repo.add_behavior(BehaviorSignal(item_id=1, action="clicked"))
        self.assertEqual(len(self.repo.list_behaviors()), 1)


if __name__ == "__main__":
    unittest.main()
