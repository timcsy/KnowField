"""T015：figure_extract 從原文抓圖、取不到回 None（best-effort，不拋）。"""

import unittest

from learnnews.media.figure_extract import extract_figure
from tests.helpers import make_item


class TestFigureExtract(unittest.TestCase):
    def test_extracts_first_img(self):
        item = make_item("新聞", external_id="1", url="https://a/1",
                         abstract='文字 <img src="https://img.example/pic.jpg"> 更多文字')
        fig = extract_figure(item)
        self.assertIsNotNone(fig)
        self.assertEqual(fig.kind, "原文")
        self.assertEqual(fig.url, "https://img.example/pic.jpg")

    def test_none_when_no_img(self):
        item = make_item("論文", external_id="2", url="https://a/2", abstract="純文字摘要")
        self.assertIsNone(extract_figure(item))  # 取不到回 None，不阻塞

    def test_none_when_empty_abstract(self):
        item = make_item("無前文", external_id="3", url="https://a/3", abstract="")
        self.assertIsNone(extract_figure(item))


if __name__ == "__main__":
    unittest.main()
