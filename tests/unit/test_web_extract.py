"""spec 030 增量：網頁正文→markdown 抽取（stdlib、離線、略過 nav/script）。"""

import unittest

from learnnews.ingest.web import extract_article_markdown

_HTML = """<html><head><title>我的文章 - 部落格</title></head><body>
<nav>首頁 關於 聯絡</nav>
<article>
<h1>大標題</h1>
<p>這是第一段內容，講述一個重要的觀念，值得收進知識庫慢慢想。</p>
<h2>小節一</h2>
<ul><li>要點一很重要要記得</li><li>要點二也不能忘</li></ul>
<script>var x = 1;</script>
<footer>版權所有 2026</footer>
</article></body></html>"""


class TestExtractArticle(unittest.TestCase):
    def test_markdown_structure(self):
        title, md = extract_article_markdown(_HTML)
        self.assertIn("我的文章", title)
        self.assertIn("# 大標題", md)
        self.assertIn("## 小節一", md)
        self.assertIn("- 要點一很重要要記得", md)
        self.assertIn("第一段內容", md)

    def test_skips_nav_script_footer(self):
        _, md = extract_article_markdown(_HTML)
        self.assertNotIn("首頁 關於", md)      # nav 略過
        self.assertNotIn("var x", md)           # script 略過
        self.assertNotIn("版權所有", md)        # footer 略過

    def test_empty_html(self):
        title, md = extract_article_markdown("<html><body></body></html>")
        self.assertEqual(md.strip(), "")


if __name__ == "__main__":
    unittest.main()
