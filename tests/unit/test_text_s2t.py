"""簡→繁顯示層正規化（spec 037）。"""
import pytest

from knowfield.text import s2t

_HAS_ENGINE = s2t.available()
needs_engine = pytest.mark.skipif(not _HAS_ENGINE, reason="未安裝 opencc（可選相依）")


class TestProtectedSegments:
    """US3：research.md 實測的六個危險案例，未保護時全部被改壞。"""

    @pytest.mark.parametrize("text,must_survive", [
        ("說明 ```python\ndef 处理(内存): return 内存.复制()\n``` 完", "def 处理(内存): return 内存.复制()"),
        ("見 http://a.cn/发展/index.html 這裡", "http://a.cn/发展/index.html"),
        ("![深入解析技术](https://pic1.zhimg.com/发展_v2.jpg)", "https://pic1.zhimg.com/发展_v2.jpg"),
        ("公式 $$ p(x) = \\int q(z)dz \\text{发展} $$ 完", "\\text{发展}"),
        ("当 $x_{发}$ 时", "x_{发}"),
        ("呼叫 `发送` 函式", "`发送`"),
    ])
    @needs_engine
    def test_protected_segment_survives_conversion(self, text, must_survive):
        out = s2t.convert(text)
        assert must_survive in out, f"承重片段被轉換破壞：{must_survive!r} 不在輸出中"

    @needs_engine
    def test_prose_around_protected_still_converts(self):
        """保護不能保過頭——承重片段以外的正文仍要轉。"""
        out = s2t.convert("这个 `发送` 软件")
        assert "`发送`" in out          # 行內程式碼原樣
        assert "這個" in out and "軟體" in out   # 正文有轉

    @needs_engine
    def test_link_text_converts_url_does_not(self):
        out = s2t.convert("見 [这个软件](https://a.cn/发展) 說明")
        assert "這個軟體" in out
        assert "https://a.cn/发展" in out


class TestConversion:
    """US1：詞彙在地化，以及非簡體輸入逐字不變。"""

    @needs_engine
    @pytest.mark.parametrize("src,expect", [
        ("这个软件", "這個軟體"),
        ("内存管理", "記憶體管理"),
        ("程序员", "程式設計師"),
        ("深入解析Flow Matching技术", "深入解析Flow Matching技術"),
    ])
    def test_vocabulary_localised(self, src, expect):
        assert s2t.convert(src) == expect

    @needs_engine
    @pytest.mark.parametrize("text", [
        "這個軟體的記憶體管理很複雜。",                  # 已是繁體
        "Flow Matching is a generative model.",     # 英文
        "「引號」、全形（括號）……",                      # 全形標點
        "",                                          # 空字串
    ])
    def test_non_simplified_unchanged(self, text):
        assert s2t.convert(text) == text

    @needs_engine
    def test_one_to_many_disambiguated(self):
        assert s2t.convert("头发很长，发展很快。") == "頭髮很長，發展很快。"

    @needs_engine
    def test_deterministic(self):
        src = "这个软件的内存管理"
        assert s2t.convert(src) == s2t.convert(src)


class TestFallback:
    """US4：引擎不可用時退回 identity，不得中斷。"""

    def test_identity_when_engine_missing(self, monkeypatch):
        monkeypatch.setattr(s2t, "_load_converter", lambda: None)
        s2t.convert.cache_clear() if hasattr(s2t.convert, "cache_clear") else None
        src = "这个软件"
        assert s2t.convert(src, _force_reload=True) == src

    def test_available_is_boolean(self):
        assert isinstance(s2t.available(), bool)
