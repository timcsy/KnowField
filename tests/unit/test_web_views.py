"""T004：entry → PageEntry 轉換。"""

import unittest

from knowfield.models import Article, DigestEntry, Figure, Item
from knowfield.web.views import entry_to_page


def _entry(headline, title, body, figkind=None):
    fig = Figure(kind=figkind, url="https://img/x") if figkind else None
    art = Article(item_id=0, body=body, source_url="https://a/1",
                  headline=headline, figure=fig)
    item = Item(source_id="s", external_id="1", title=title, url="https://a/1")
    return DigestEntry(item=item, rank=1, relevance_score=0.9, article=art)


class TestWebViews(unittest.TestCase):
    def test_paragraphs_split(self):
        pe = entry_to_page(_entry("標題", "標題", "第一段。\n\n第二段。"))
        self.assertEqual(pe.paragraphs, ["第一段。", "第二段。"])

    def test_show_original_when_headline_differs(self):
        pe = entry_to_page(_entry("整理標題", "Original", "x"))
        self.assertTrue(pe.show_original)
        pe2 = entry_to_page(_entry("同", "同", "x"))
        self.assertFalse(pe2.show_original)

    def test_figure_is_ai_flag(self):
        pe = entry_to_page(_entry("h", "t", "x", figkind="AI 示意"))
        self.assertTrue(pe.figure.is_ai)
        self.assertEqual(pe.figure.label, "AI 示意・非原文")
        pe2 = entry_to_page(_entry("h", "t", "x", figkind="原文"))
        self.assertFalse(pe2.figure.is_ai)

    def test_raw_entry_no_article(self):
        item = Item(source_id="s", external_id="1", title="標題", url="https://a/1")
        pe = entry_to_page(DigestEntry(item=item, rank=1, relevance_score=0.0,
                                       article=None))
        self.assertEqual(pe.headline, "標題")
        self.assertEqual(pe.paragraphs, [])


if __name__ == "__main__":
    unittest.main()
