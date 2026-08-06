"""T022：興趣相關性排序。"""

import unittest

from knowfield.ranking.relevance import RelevanceRanker
from tests.helpers import make_item


class TestRanking(unittest.TestCase):
    def setUp(self):
        self.ranker = RelevanceRanker(threshold=0.05)

    def test_relevant_kept_irrelevant_filtered(self):
        relevant = make_item("LLM 推理 最佳化", external_id="1", url="https://a")
        irrelevant = make_item("貓咪 攝影 教學", external_id="2", url="https://b")
        scored = self.ranker.rank([relevant, irrelevant], ["LLM 推理"])
        titles = [s.item.title for s in scored]
        self.assertIn("LLM 推理 最佳化", titles)
        self.assertNotIn("貓咪 攝影 教學", titles)

    def test_matched_topic_recorded(self):
        it = make_item("agent 規劃", external_id="1", url="https://a")
        scored = self.ranker.rank([it], ["agent", "編譯器"])
        self.assertEqual(scored[0].matched_topic, "agent")

    def test_no_topics_keeps_all(self):
        items = [make_item("任意", external_id="1"), make_item("任意二", external_id="2")]
        scored = self.ranker.rank(items, [])
        self.assertEqual(len(scored), 2)

    def test_learned_weight_boosts_score(self):
        it = make_item("agent 規劃", external_id="1", url="https://a")
        base = self.ranker.rank([it], ["agent"])[0].score
        boosted = self.ranker.rank([it], ["agent"], {"agent": 1.0})[0].score
        self.assertGreater(boosted, base)


if __name__ == "__main__":
    unittest.main()
