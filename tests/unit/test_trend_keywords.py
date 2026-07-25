"""T003/T004 [US1]：trend_keywords 純函式——高頻排序、中英混合、停用詞/門檻過濾。零外部呼叫。"""

import unittest

from learnnews.trend.keywords import trend_keywords


class TestTrendKeywords(unittest.TestCase):
    def test_high_frequency_first_and_topn(self):
        titles = [
            "latent reasoning breakthrough",
            "latent reasoning survey",
            "latent reasoning benchmark",
            "diffusion planning agent",
            "diffusion planning results",
            "retrieval augmented notes",
        ]
        rs = trend_keywords(titles, top_n=3, min_count=2)
        self.assertEqual(rs[0], "latent")                     # latent/reasoning 同 3 次，latent 先出現→排前（stable）
        self.assertIn("reasoning", rs)
        self.assertIn("diffusion", rs)                        # 2 次
        self.assertLessEqual(len(rs), 3)                      # top_n 裁切

    def test_min_count_and_stopwords_filtered(self):
        titles = ["the new model of learning", "a model paper", "using the method"]
        rs = trend_keywords(titles, min_count=2)
        # model 出現 2 次但屬領域泛詞停用詞 → 濾掉；the/a/of/new/using/paper/method 皆停用或單次
        self.assertNotIn("model", rs)
        self.assertNotIn("the", rs)
        self.assertEqual(rs, [])                              # 全被濾 → []

    def test_chinese_bigrams(self):
        titles = ["大模型的推理能力", "推理能力評測", "長程推理與記憶"]
        rs = trend_keywords(titles, min_count=2, top_n=8)
        self.assertIn("推理", rs)                             # 中文 bigram 高頻（3 次）
        # 「能力」出現 2 次也應在
        self.assertIn("能力", rs)

    def test_stable_on_ties_and_custom_stopwords(self):
        titles = ["alpha beta", "alpha beta", "gamma delta", "gamma delta"]
        rs = trend_keywords(titles, min_count=2, top_n=4)
        self.assertEqual(rs[0], "alpha")                      # 同分保首次出現順序
        rs2 = trend_keywords(titles, min_count=2, stopwords={"alpha"})
        self.assertNotIn("alpha", rs2)                        # 傳入停用詞可擴充

    def test_empty(self):
        self.assertEqual(trend_keywords([], min_count=2), [])
        self.assertEqual(trend_keywords(["", "  "], min_count=2), [])


if __name__ == "__main__":
    unittest.main()
