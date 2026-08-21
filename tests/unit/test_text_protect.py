"""承重片段佔位保護（spec 037，FR-006）。

research.md 實測：未保護的簡→繁轉換會改壞程式碼識別字、URL、圖片路徑與數學下標。
這裡釘住的是「抽佔位 → 塞回」這條管線本身的正確性。
"""
import pytest

from knowfield.text import protect


class TestRoundTrip:
    """最重要的不變式：restore(*mask(t)) == t，對任意輸入成立。"""

    @pytest.mark.parametrize("text", [
        "",
        "純文字沒有任何承重片段",
        "只有一個 `行內程式碼`",
        "```python\nprint(1)\n```",
        "$$ x = 1 $$",
        "![圖](a.png) 和 [連結](b.html) 和 https://c.dev",
        "混合：`a` $b$ ```c``` $$d$$ ![e](f) [g](h) https://i.j",
        # 巢狀：fenced 內部含 $ 與反引號，不得被行內規則拆開
        "```md\n這裡有 $x$ 和 `code` 和 https://inner.example\n```",
        "行內數學相鄰：$a$$b$ 兩個獨立公式",
        "連續空行\n\n\n和尾端空白   \n",
    ])
    def test_round_trip(self, text):
        masked, segments = protect.mask(text)
        assert protect.restore(masked, segments) == text

    def test_segment_count_matches_placeholders(self):
        text = "`a` 和 `b` 和 `c`"
        masked, segments = protect.mask(text)
        assert len(segments) == 3
        for i in range(len(segments)):
            assert protect.placeholder(i) in masked


class TestCategories:
    """data-model.md 列的七類承重片段，各一例。"""

    @pytest.mark.parametrize("text,protected", [
        ("前 ```python\ndef 处理(内存): pass\n``` 後", "def 处理(内存): pass"),
        ("前 ~~~\n内存\n~~~ 後", "内存"),
        ("前 $$ \\text{发展} $$ 後", "\\text{发展}"),
        ("前 $x_{发}$ 後", "x_{发}"),
        ("前 `发送` 後", "发送"),
        ("前 ![深入解析技术](https://a.cn/发展_v2.jpg) 後", "发展_v2.jpg"),
        ("前 https://a.cn/发展/index.html 後", "发展"),
    ])
    def test_category_is_masked(self, text, protected):
        masked, segments = protect.mask(text)
        assert protected not in masked, f"承重片段未被抽走：{protected}"
        assert any(protected in s for s in segments)


class TestLinkTextStaysVisible:
    """data-model.md 第 4 條：連結的顯示文字要轉，只保護 (url)。"""

    def test_link_text_not_masked_but_url_is(self):
        masked, segments = protect.mask("見 [这个软件](https://a.cn/发展) 說明")
        assert "这个软件" in masked, "連結顯示文字是正文，必須留在可轉換的部分"
        assert "发展" not in masked, "連結 URL 必須被保護"

    def test_image_alt_is_masked_whole(self):
        """圖片相反：整段抽（alt 常與檔名對應，且極少需要閱讀）。"""
        masked, segments = protect.mask("![深入解析技术](https://a.cn/图.jpg)")
        assert "技术" not in masked
        assert "图.jpg" not in masked


class TestPlaceholderIsTransformSafe:
    """佔位符本身不得被 s2twp 動到——否則塞回時對不上（T006）。"""

    def test_placeholder_is_pure_ascii(self):
        ph = protect.placeholder(0)
        assert ph.isascii(), f"佔位符必須是純 ASCII，實際：{ph!r}"

    def test_placeholder_survives_conversion(self):
        opencc = pytest.importorskip("opencc")
        conv = opencc.OpenCC("s2twp")
        for i in (0, 7, 42, 999):
            ph = protect.placeholder(i)
            assert conv.convert(ph) == ph, f"佔位符被轉換器改動：{ph!r}"


class TestInlineMathWithNewline:
    """⚠️ 前後端的數學辨識規則必須一致。

    前端 `Markdown.tsx` 的行內數學**容許單一換行**（不跨空行），註解寫明理由：
    「否則含換行的行內數學漏抓、留下落單 `$` 造成後續配對連鎖崩壞」。
    而後端 `protect.py` 用的是 `\\$[^$\\n]+\\$`（不容許換行）——於是同一條公式
    **前端當數學渲染、後端翻譯時不保護**，會原封送進 LLM 被改寫。

    兩處各有一套規則就會漂開；這組測試把它們釘在一起。
    """

    def test_inline_math_with_single_newline_is_protected(self):
        text = "The value $a\n= b$ appears here."
        masked, segments = protect.mask(text)
        assert len(segments) == 1, f"含換行的行內數學沒被保護：{segments}"
        assert "$a\n= b$" in segments[0]

    def test_inline_math_does_not_span_blank_line(self):
        """跨空行不算——那通常是兩個落單的 $，硬吞會連鎖崩壞（與前端同一判準）。"""
        text = "price is $5\n\nand $10 here"
        masked, segments = protect.mask(text)
        assert not any("\n\n" in s for s in segments)

    def test_round_trip_still_holds(self):
        for t in ["$a\n= b$", "prose $x\ny$ more", "$$a\n\nb$$"]:
            assert protect.restore(*protect.mask(t)) == t
