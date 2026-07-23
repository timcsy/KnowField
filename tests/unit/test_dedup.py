"""T021：去重精確層＋語義層。"""

import unittest

from learnnews.dedup.exact import group_exact
from learnnews.dedup.semantic import deduplicate
from tests.helpers import make_item


class TestDedup(unittest.TestCase):
    def test_exact_same_external_id(self):
        a = make_item("論文標題", external_id="2401.001", url="https://a")
        b = make_item("論文標題（轉貼）", external_id="2401.001", url="https://b")
        groups = group_exact([a, b])
        self.assertEqual(len(groups), 1)  # 相同 external_id → 同群

    def test_exact_distinct(self):
        a = make_item("A 論文", external_id="1", url="https://a")
        b = make_item("B 論文", external_id="2", url="https://b")
        self.assertEqual(len(group_exact([a, b])), 2)

    def test_semantic_merges_paraphrase(self):
        # 不同 external_id、幾乎相同標題 → 語義層合併
        a = make_item("大型語言模型的推理最佳化方法", external_id="x1", url="https://a")
        b = make_item("大型語言模型的推理最佳化方法", external_id="x2", url="https://b")
        clusters = deduplicate([a, b], threshold=0.82)
        self.assertEqual(len(clusters), 1)

    def test_semantic_keeps_distinct(self):
        a = make_item("大型語言模型推理", external_id="x1", url="https://a")
        b = make_item("貓咪攝影教學指南", external_id="x2", url="https://b")
        clusters = deduplicate([a, b], threshold=0.82)
        self.assertEqual(len(clusters), 2)


if __name__ == "__main__":
    unittest.main()
