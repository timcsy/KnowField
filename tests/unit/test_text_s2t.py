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


class TestVocabularyOverrides:
    """FR-010：s2twp 的詞彙層會轉到錯的領域義。這 8 個是在實際語料上觀察到的錯義／不成詞。"""

    @needs_engine
    @pytest.mark.parametrize("src,must_contain,must_not_contain", [
        ("模型的参数需要学习", "參數", "引數"),          # 模型參數 ≠ 函式引數
        ("由此推导出结论", "推導出", "推匯出"),           # 推匯出不成詞
        ("检索范式的转变", "範式", "正規化"),             # paradigm ≠ normalization
        ("CNFs是NFs的扩展", "擴展", "擴充套件"),          # 數學擴展 ≠ 軟體擴充套件
        ("在图像生成中", "圖像", "影象"),                # 影象不成詞
        ("寻找全局最优解", "全局", "全域性"),
        ("多任务学习", "多任務", "多工"),
        ("需要更高的权限", "權限", "許可權"),
    ])
    def test_known_bad_mapping_corrected(self, src, must_contain, must_not_contain):
        out = s2t.convert(src)
        assert must_contain in out, f"{src!r} → {out!r}"
        assert must_not_contain not in out, f"錯誤映射未修正：{src!r} → {out!r}"

    @needs_engine
    def test_override_does_not_break_traditional_input(self):
        """FR-008 不得被 FR-010 破壞：作者本來就寫「引數」時那是他的用字，不動。"""
        src = "函式的引數列表"
        assert s2t.convert(src) == src

    @needs_engine
    def test_override_skips_when_both_forms_present(self):
        """原文同時出現兩種寫法 → 保守跳過（少修比改壞安全，同 FR-006 方向）。"""
        src = "函式的引數與模型的参数不同"
        out = s2t.convert(src)
        assert "引數" in out          # 原文那個保留

    @needs_engine
    def test_correct_localisations_still_apply(self):
        """別修過頭——正確的台灣用語轉換必須留著。"""
        out = s2t.convert("优化目标函数中的数据和概率与网络")
        for w in ["最佳化", "函式", "資料", "機率", "網路"]:
            assert w in out, f"正確的在地化被誤傷：{w} 不在 {out!r}"


class TestFallback:
    """US4：引擎不可用時退回 identity，不得中斷。"""

    def test_identity_when_engine_missing(self, monkeypatch):
        monkeypatch.setattr(s2t, "_load_converter", lambda: None)
        s2t.convert.cache_clear() if hasattr(s2t.convert, "cache_clear") else None
        src = "这个软件"
        assert s2t.convert(src, _force_reload=True) == src

    def test_available_is_boolean(self):
        assert isinstance(s2t.available(), bool)
