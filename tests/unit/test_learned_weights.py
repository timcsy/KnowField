"""T043：learned_weights 由行為訊號計算。"""

import unittest

from learnnews.interests.learning import learn, merge_into_profile


class TestLearnedWeights(unittest.TestCase):
    def test_clicks_produce_weight(self):
        w = learn([("agent", "clicked"), ("agent", "clicked"), ("agent", "clicked"),
                   ("編譯器", "skipped")])
        self.assertEqual(w["agent"], 1.0)
        self.assertEqual(w["編譯器"], 0.0)

    def test_empty(self):
        self.assertEqual(learn([]), {})

    def test_merge_keeps_only_explicit(self):
        merged = merge_into_profile(["agent"], {"agent": 1.0, "編譯器": 0.8})
        self.assertEqual(merged, {"agent": 1.0})  # 明講之外的權重被丟棄


if __name__ == "__main__":
    unittest.main()
