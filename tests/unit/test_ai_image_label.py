"""T016：AI 圖必標「AI 示意・非原文」（FR-007）。"""

import unittest

from learnnews.media.ai_image import StubAIImage
from learnnews.models import Figure
from learnnews.summarize.article import ArticleBuilder
from tests.helpers import make_item


class TestAIImageLabel(unittest.TestCase):
    def test_figure_label(self):
        self.assertEqual(Figure(kind="AI 示意", url="x").label(), "AI 示意・非原文")
        self.assertEqual(Figure(kind="原文", url="x", source_note="取自原文").label(),
                         "取自原文")

    def test_stub_ai_image_is_labeled(self):
        fig = StubAIImage()(make_item("t", external_id="1"))
        self.assertEqual(fig.kind, "AI 示意")
        self.assertEqual(fig.label(), "AI 示意・非原文")

    def test_ai_image_used_only_when_no_source_figure(self):
        # 無原文圖＋啟用 AI 圖 → 用 AI 示意圖並標示
        item = make_item("無圖標題", external_id="2", url="https://a/2", abstract="純文字")
        a = ArticleBuilder(ai_image_gen=StubAIImage()).build(
            item, "agent", with_image=True, ai_image=True)
        self.assertIsNotNone(a.figure)
        self.assertEqual(a.figure.kind, "AI 示意")

    def test_no_ai_image_when_not_enabled(self):
        item = make_item("無圖標題", external_id="3", url="https://a/3", abstract="純文字")
        a = ArticleBuilder(ai_image_gen=StubAIImage()).build(
            item, "agent", with_image=True, ai_image=False)
        self.assertIsNone(a.figure)  # 未啟用 → 純文字


if __name__ == "__main__":
    unittest.main()
