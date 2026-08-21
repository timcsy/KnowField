"""來源語言判定（spec 038，FR-009）。用 CJK 佔比，零相依。"""
import pytest

from knowfield.text import lang


class TestIsEnglish:
    @pytest.mark.parametrize("text", [
        "Given a data point sampled from a real data distribution, we define a forward process.",
        "Attention Is All You Need. The dominant sequence transduction models are based on RNNs.",
        "$x = f(z)$ where $f$ is invertible and differentiable everywhere.",
    ])
    def test_english_is_english(self, text):
        assert lang.is_english(text) is True

    @pytest.mark.parametrize("text", [
        "這個軟體的記憶體管理很複雜，程式設計師需要學習。",
        "深入解析Flow Matching技術，梳理其核心概念與數學原理。",
        "Flow-based Model是一種基於Normalizing Flows的生成模型。",   # 中英混排，仍是中文文章
    ])
    def test_chinese_is_not_english(self, text):
        assert lang.is_english(text) is False

    def test_empty_is_not_english(self):
        """空內容沒有可翻的東西 → 不提供翻譯動作。"""
        assert lang.is_english("") is False
        assert lang.is_english("   \n  ") is False

    def test_english_article_quoting_chinese_terms_still_english(self):
        """英文長文引用幾個中文術語不該被判成中文文章。

        ⚠️ 這條的第一版寫成 `"The Chinese term is 擴散..." * 10`——38 個非空白字元塞 2 個中文
        ＝ 5.3%，超過閾值所以失敗。但那個密度在真實文章裡不存在（4 萬字的英文文章引用 20 個
        中文術語約 0.1%）。**測試樣本不真實時，失敗的是測試不是實作**——改成真實密度。
        """
        article = ("The dominant sequence transduction models are based on complex recurrent "
                   "or convolutional neural networks. We propose a new simple architecture. ") * 12
        article += "Some sources use the term 擴散模型 for this family."
        assert lang.cjk_ratio(article) < 0.01
        assert lang.is_english(article) is True

    def test_deterministic(self):
        t = "Some English text here."
        assert lang.is_english(t) == lang.is_english(t)
