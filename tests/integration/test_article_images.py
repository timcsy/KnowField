"""T017：原文圖內嵌（情境 E）＋AI 圖標示（情境 F）。"""

import unittest

from learnnews.media.figure_extract import extract_figure
from learnnews.media.ai_image import StubAIImage
from learnnews.summarize.article import ArticleBuilder
from learnnews.cli.pull_render import render
from learnnews.pull.service import PullService
from learnnews.cli.pull_cmd import run_pull
from tests.helpers import FakeAdapter, make_item


class TestArticleImages(unittest.TestCase):
    def test_source_figure_embedded(self):
        item = make_item("agent 新聞", external_id="1", url="https://a/1",
                         abstract='agent 內文 <img src="https://img/x.jpg"> 更多')
        svc = PullService(article_builder=ArticleBuilder(figure_extractor=extract_figure))
        result = run_pull([FakeAdapter("s", [item])], "agent", service=svc)
        out = render(result, "markdown")
        self.assertIn("https://img/x.jpg", out)
        self.assertIn("取自原文", out)

    def test_ai_figure_labeled_when_no_source(self):
        item = make_item("無圖主題文章", external_id="2", url="https://a/2", abstract="純文字")
        svc = PullService(article_builder=ArticleBuilder(
            figure_extractor=extract_figure, ai_image_gen=StubAIImage()))
        result = run_pull([FakeAdapter("s", [item])], "無圖主題文章",
                          service=svc, ai_image=True)
        out = render(result, "markdown")
        self.assertIn("AI 示意・非原文", out)  # FR-007 必標示


if __name__ == "__main__":
    unittest.main()
