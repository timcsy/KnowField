"""T005：ArticleBuilder 產散文＋忠實／優雅降級。"""

import unittest

from learnnews.backends.openai_api import OpenAIError
from learnnews.summarize.article import ArticleBuilder
from tests.helpers import make_item


class _FailBackend:
    def write_article(self, title, abstract, matched_topic):
        raise OpenAIError("模擬後端失敗")


class TestArticleBuilder(unittest.TestCase):
    def test_produces_prose_from_source(self):
        item = make_item("agent 記憶機制", external_id="1", url="https://a/1",
                         abstract="這是關於 agent 記憶的前文。")
        a = ArticleBuilder().build(item, "agent")
        self.assertIn("agent 記憶機制", a.body)       # 依原文標題
        self.assertIn("agent 記憶", a.body)            # 帶入原文前文
        self.assertEqual(a.source_url, "https://a/1")  # 一鍵原文
        self.assertFalse(a.degraded)

    def test_no_fabrication_when_title_only(self):
        # 原文只有標題、無數據 → stub 不捏造數字
        item = make_item("某新聞標題", external_id="2", url="https://a/2", abstract="")
        a = ArticleBuilder().build(item, "")
        self.assertIn("某新聞標題", a.body)
        # 不應憑空出現百分比等數據
        self.assertNotIn("%", a.body)

    def test_headline_from_backend(self):
        class _Backend:
            def write_article(self, title, abstract, matched_topic):
                return "整理過的新聞標題", "本體散文。"
        item = make_item("Some English Paper Title", external_id="9", url="https://a/9")
        a = ArticleBuilder(backend=_Backend()).build(item, "agent")
        self.assertEqual(a.headline, "整理過的新聞標題")
        self.assertEqual(a.body, "本體散文。")

    def test_stub_headline_defaults_to_title(self):
        item = make_item("原標題", external_id="8", url="https://a/8", abstract="x")
        a = ArticleBuilder().build(item, "agent")
        self.assertEqual(a.headline, "原標題")   # 離線無法整理 → 退回原標題

    def test_graceful_degrade_on_backend_failure(self):
        item = make_item("agent", external_id="3", url="https://a/3")
        a = ArticleBuilder(backend=_FailBackend()).build(item, "agent")
        self.assertTrue(a.degraded)                    # FR-011：降級不拋
        self.assertIn("消化暫不可用", a.body)
        self.assertEqual(a.source_url, "https://a/3")  # 仍保留原文連結


if __name__ == "__main__":
    unittest.main()
