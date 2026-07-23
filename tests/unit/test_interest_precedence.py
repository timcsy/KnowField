"""T038：明講優先於學習——被移除的主題不因學習權重復活（憲章原則 VI）。"""

import unittest

from learnnews.interests.service import InterestService
from learnnews.models import InterestProfile
from learnnews.ranking.relevance import RelevanceRanker
from learnnews.store.repository import Repository
from tests.helpers import make_item


class TestInterestPrecedence(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(":memory:")
        self.svc = InterestService(self.repo)

    def tearDown(self):
        self.repo.close()

    def test_remove_clears_learned_weight(self):
        self.repo.save_interest_profile(InterestProfile(
            explicit_topics=["編譯器", "agent"],
            learned_weights={"編譯器": 1.0, "agent": 0.3}))
        self.svc.remove("編譯器")
        p = self.repo.get_interest_profile()
        self.assertNotIn("編譯器", p.explicit_topics)
        self.assertNotIn("編譯器", p.learned_weights)  # 學習權重一併清除

    def test_removed_topic_not_matched_even_if_learned(self):
        # 即使排序器拿到殘留的學習權重，只要不在明講清單就不比對
        ranker = RelevanceRanker(threshold=0.05)
        item = make_item("編譯器 最佳化", external_id="1", url="https://a/1")
        scored = ranker.rank([item], explicit_topics=["agent"],
                             learned_weights={"編譯器": 1.0})
        # 明講只有 agent；編譯器條目與 agent 無關 → 被濾除
        self.assertEqual(scored, [])


if __name__ == "__main__":
    unittest.main()
