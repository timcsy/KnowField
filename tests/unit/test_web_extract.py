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
        self.assertEqual(title, "大標題")     # 文章 h1＝標題（勝過帶站名後綴的 <title>）
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

    def test_images_to_markdown(self):
        html = ('<article><h1>圖文</h1><p>看這張圖：</p>'
                '<img src="https://pic.example/cat.jpg" alt="一隻貓">'
                '<img src="//cdn.example/dog.png"></article>')
        _, md = extract_article_markdown(html)
        self.assertIn("![一隻貓](https://pic.example/cat.jpg)", md)
        self.assertIn("![](https://cdn.example/dog.png)", md)   # // 補成 https:

    def test_equation_images_to_latex(self):
        # 知乎式公式圖：tex 在 URL 的 ?tex= 或 alt；行內數學留句中、獨立成 $$區塊$$
        html = ('<article><p>向量場 <img src="//www.zhihu.com/equation?tex=u_t%28x%29" '
                'alt="u_t(x)" eeimg="1"> 是待學的。</p>'
                '<img src="//www.zhihu.com/equation?tex=%5Cmin_%5Ctheta%20L" alt="\\min_\\theta L"></article>')
        _, md = extract_article_markdown(html)
        self.assertIn("$u_t(x)$", md)                 # 行內公式還原、句子不斷
        self.assertIn("向量場", md)
        self.assertIn("$$", md)                        # 獨立公式成區塊
        self.assertIn("\\min_\\theta L", md)

    def test_katex_annotation_math(self):
        # KaTeX/MathML 標準載體：<annotation encoding="application/x-tex">TEX</annotation>
        html = ('<p>設 <span class="katex"><span class="katex-mathml"><math><semantics>'
                '<mrow>RENDER</mrow><annotation encoding="application/x-tex">x^2+y^2</annotation>'
                '</semantics></math></span><span class="katex-html" aria-hidden="true">VISUAL</span>'
                '</span> 成立。</p>')
        _, md = extract_article_markdown(html)
        self.assertIn("$x^2+y^2$", md)
        self.assertIn("設", md)
        self.assertIn("成立", md)
        self.assertNotIn("RENDER", md)      # mathml 渲染跳過
        self.assertNotIn("VISUAL", md)      # katex-html 視覺渲染跳過

    def test_mathjax_script_math(self):
        # MathJax v2 標準載體：<script type="math/tex">TEX</script>
        html = '<p>公式 <script type="math/tex">\\sum_i a_i</script> 如上。</p>'
        _, md = extract_article_markdown(html)
        self.assertIn("$\\sum_i a_i$", md)
        self.assertIn("公式", md)

    def test_span_datatex_inline_math(self):
        # 知乎行內數學＝<span data-tex>，內部是渲染 SVG → 取 tex、跳過渲染物、句子不斷
        html = ('<article><p>向量場 '
                '<span class="ztext-math" data-tex="u_t(x)"><svg><path d="M0"/></svg>RENDER</span>'
                ' 是待學的。</p></article>')
        _, md = extract_article_markdown(html)
        self.assertIn("$u_t(x)$", md)
        self.assertIn("向量場", md)
        self.assertIn("是待學的", md)
        self.assertNotIn("RENDER", md)          # 內部渲染節點被跳過

    def test_title_from_h1_even_in_header(self):
        # 文章真標題常在 <header> 裡（會被 _SKIP 略過內文）→ 仍要當標題，且勝過第一個章節
        html = ('<article><header class="Post-Header"><h1>文章真正的標題</h1>'
                '<div>作者 · 100 贊同</div></header>'
                '<h2>一、第一節</h2><p>內文…</p></article>')
        title, md = extract_article_markdown(html)
        self.assertEqual(title, "文章真正的標題")     # 真標題（來自 header 裡的 h1）
        self.assertNotIn("100 贊同", md)               # header 其餘仍略過

    def test_consecutive_duplicate_images_deduped(self):
        # 知乎懶載：模糊預覽圖＋真圖＝同一張連續兩個 <img> → 去重
        html = ('<article><p>看圖：</p>'
                '<img src="https://pic.example/cat.jpg" alt="預覽">'
                '<img src="https://pic.example/cat.jpg" alt="貓">'
                '<img src="https://pic.example/dog.jpg"></article>')
        _, md = extract_article_markdown(html)
        self.assertEqual(md.count("pic.example/cat.jpg"), 1)   # 連續同圖只留一個
        self.assertIn("pic.example/dog.jpg", md)

    def test_figure_and_lazy_image(self):
        # 解說圖常包在 <figure> 裡、且是懶載入（真網址在 data-original，src 是佔位符）
        html = ('<article><h2>解說</h2>'
                '<figure><img src="data:image/gif;base64,PLACEHOLDER" '
                'data-original="https://pic.example/diagram.png" alt="示意圖">'
                '<figcaption>圖一</figcaption></figure></article>')
        _, md = extract_article_markdown(html)
        self.assertIn("![示意圖](https://pic.example/diagram.png)", md)  # 圖沒被 figure 吞、取到真網址


if __name__ == "__main__":
    unittest.main()
