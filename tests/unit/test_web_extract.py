"""spec 030 增量：網頁正文→markdown 抽取（stdlib、離線、略過 nav/script）。"""

import unittest

from knowfield.ingest.web import (
    extract_article_markdown, normalize_ingest_url, _merge_math_blocks,
    _normalize_headings, _clean_chars,
)

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
        self.assertNotIn("# 大標題", md)      # 標題另外顯示、不在內文重複（層次正規化）
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

    def test_relative_image_resolved_with_base_url(self):
        # 相對路徑圖片（多數部落格用法）：有 base_url→接成絕對；無 base_url→丟（無法解析）
        html = ('<article><p>看圖：</p><img src="img/diagram.png" alt="示意圖">'
                '<img src="../fig/chart.svg"></article>')
        _, md = extract_article_markdown(html, base_url="https://blog.example/posts/2024-x/")
        self.assertIn("![示意圖](https://blog.example/posts/2024-x/img/diagram.png)", md)
        self.assertIn("(https://blog.example/posts/fig/chart.svg)", md)   # ../ 正確上溯
        _, md2 = extract_article_markdown(html)                # 沒 base_url→相對圖丟（維持舊行為）
        self.assertNotIn("diagram.png", md2)

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


class TestListAndTable(unittest.TestCase):
    def test_li_with_nested_p_and_tag_marker(self):
        # LaTeXML 式 <li><span class=ltx_tag>•</span><div><p>內容</p></div>：內容要進 li、別空成 - •
        html = ('<article><ul><li><span class="ltx_tag ltx_tag_item">•</span>'
                '<div class="ltx_para"><p>第一項的完整內容在這裡</p></div></li>'
                '<li><span class="ltx_tag">•</span><p>第二項內容也完整</p></li></ul></article>')
        _, md = extract_article_markdown(html)
        self.assertIn("- 第一項的完整內容在這裡", md)
        self.assertIn("- 第二項內容也完整", md)
        self.assertNotIn("- •", md)                     # 沒有空 bullet

    def test_data_table_to_markdown(self):
        html = ('<article><table class="ltx_tabular"><thead><tr>'
                '<th>Layer</th><th>Cost</th></tr></thead><tbody>'
                '<tr><td>Self-Attention</td><td>fast</td></tr>'
                '<tr><td>Recurrent</td><td>slow</td></tr></tbody></table></article>')
        _, md = extract_article_markdown(html)
        self.assertIn("| Layer | Cost |", md)
        self.assertIn("| --- | --- |", md)
        self.assertIn("| Self-Attention | fast |", md)

    def test_equation_table_stays_math_not_data(self):
        # 公式表 ltx_eqn 不該變 markdown 表格（維持數學流）
        html = ('<article><table class="ltx_equation ltx_eqn_table"><tr><td>'
                '<math><semantics><annotation encoding="application/x-tex">a=b</annotation>'
                '</semantics></math></td></tr></table></article>')
        _, md = extract_article_markdown(html)
        self.assertNotIn("|", md)
        self.assertIn("$", md)


class TestHeadingNormalize(unittest.TestCase):
    def test_deep_start_lifted_to_h2(self):
        # ycc 式：內文從 h3 起跳（無 h1/h2）→ 提到 ## 起、連續
        out = _normalize_headings(["### 認識X", "內文", "#### 子節", "##### Next articles"], "某文標題")
        self.assertEqual(out[0], "## 認識X")               # h3→h2
        self.assertEqual(out[2], "### 子節")                # h4→h3
        self.assertEqual(out[3], "#### Next articles")      # h5→h4

    def test_title_duplicate_dropped_and_h1_sections_demoted(self):
        # lilianweng 式：標題重複的 heading 移除；跟標題同級的 h1 sections 降到 ## 在標題下
        out = _normalize_headings(["# 擴散模型", "前言", "# 條件生成", "## 子節"], "擴散模型")
        self.assertNotIn("# 擴散模型", out)                 # 與標題重複→移除
        self.assertEqual(out, ["前言", "## 條件生成", "### 子節"])

    def test_clean_chars_strips_invisible(self):
        self.assertEqual(_clean_chars("a\u200bb\u00a0c\ufeff"), "ab c")  # 零寬移除、NBSP→空白、BOM移除


class TestMergeMathBlocks(unittest.TestCase):
    def test_merges_consecutive_into_aligned(self):
        # arxiv 把對齊式拆成多個 $$；合併成單一 \begin{aligned}（修跑版＋消連續 $$）
        blocks = ["文字", "$$\n\\displaystyle A(x)\n$$", "$$\n\\displaystyle =B(x)\n$$", "後文"]
        out = _merge_math_blocks(blocks)
        math = [b for b in out if "$$" in b]
        self.assertEqual(len(math), 1)                       # 兩塊→一塊
        self.assertEqual(math[0].count("$$"), 2)             # 單一對 $$
        self.assertIn("\\begin{aligned}", math[0])
        self.assertIn("A(x) &=B(x)", math[0])                # 關係符號開頭→接上一列（對齊）
        self.assertNotIn("\\displaystyle", math[0])          # 去掉 \displaystyle

    def test_single_block_unchanged(self):
        self.assertEqual(_merge_math_blocks(["$$\n\\displaystyle x=1\n$$"]), ["$$\nx=1\n$$"])


class TestNormalizeIngestUrl(unittest.TestCase):
    def test_arxiv_abs_and_pdf_route_to_html_store_abs(self):
        self.assertEqual(
            normalize_ingest_url("https://arxiv.org/abs/1706.03762"),
            ("https://arxiv.org/html/1706.03762", "https://arxiv.org/abs/1706.03762"))
        self.assertEqual(                                    # pdf 也一樣
            normalize_ingest_url("https://arxiv.org/pdf/1706.03762"),
            ("https://arxiv.org/html/1706.03762", "https://arxiv.org/abs/1706.03762"))
        self.assertEqual(                                    # 版本號剝掉→正規 /abs
            normalize_ingest_url("https://arxiv.org/abs/1706.03762v7")[1],
            "https://arxiv.org/abs/1706.03762")

    def test_non_arxiv_passthrough(self):
        self.assertEqual(normalize_ingest_url("https://blog.x/post"),
                         ("https://blog.x/post", "https://blog.x/post"))


if __name__ == "__main__":
    unittest.main()
