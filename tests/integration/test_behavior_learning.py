"""T042：反覆點擊提升排序，且明講覆寫優先（US3）。"""

import unittest

from learnnews.interests.behavior import BehaviorRecorder
from learnnews.interests.learning import learn
from learnnews.ranking.relevance import RelevanceRanker
from learnnews.store.repository import Repository
from tests.helpers import make_item


class TestBehaviorLearning(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")
        self.ranker = RelevanceRanker(threshold=0.05)
        self.agent_item = make_item("agent 規劃記憶", external_id="1", url="https://a/1")
        self.comp_item = make_item("編譯器 最佳化重構", external_id="2", url="https://a/2")

    def tearDown(self):
        self.repo.close()

    def test_repeated_clicks_raise_ranking(self):
        topics = ["agent", "編譯器"]
        base = self.ranker.rank([self.agent_item, self.comp_item], topics)
        # 基準：編譯器條目通常分數較高
        base_top = base[0].item.external_id

        # 模擬反覆點擊 agent 條目 → 記錄行為 → 學習權重
        rec = BehaviorRecorder(self.repo)
        for _ in range(3):
            rec.record(item_id=1, action="clicked")
        weights = learn([("agent", "clicked")] * 3)

        boosted = self.ranker.rank([self.agent_item, self.comp_item], topics, weights)
        self.assertEqual(boosted[0].item.external_id, "1")  # agent 條目升到第一
        self.assertEqual(len(self.repo.list_behaviors()), 3)

    def test_explicit_override_beats_learning(self):
        # 學到偏好 agent，但使用者明講只要編譯器 → agent 條目不出現
        scored = self.ranker.rank([self.agent_item], explicit_topics=["編譯器"],
                                  learned_weights={"agent": 1.0})
        self.assertEqual(scored, [])


if __name__ == "__main__":
    unittest.main()
