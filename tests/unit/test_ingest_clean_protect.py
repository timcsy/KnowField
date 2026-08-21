"""收進時的深度清理不得改壞承重內容（數學／程式碼／URL／圖片）。"""
from knowfield.ingest.clean import clean_markdown


class _Mangler:
    """模擬一個不守規矩的模型：把數學與程式碼改寫掉。"""
    def reply(self, messages):
        t = messages[-1]["content"]
        return t.replace("$", "").replace("\\alpha", "alpha").replace("```", "")


class _Dropper:
    def reply(self, messages):
        return "完全不同的內容"


def test_math_survives_a_mangling_backend():
    src = "說明\n\n$$ \\alpha + \\beta $$\n\n和行內 $x_t$ 與 ```py\ncode()\n``` 結束。"
    out = clean_markdown(src, _Mangler())
    assert "$$ \\alpha + \\beta $$" in out, f"數學區塊被改壞：{out!r}"
    assert "$x_t$" in out, f"行內數學被改壞：{out!r}"
    assert "```py\ncode()\n```" in out, f"程式碼被改壞：{out!r}"


def test_backend_none_returns_source():
    src = "$x$ 原文"
    assert clean_markdown(src, None) == src


def test_no_math_still_cleans():
    """沒有承重內容時，清理照常運作（不能因為保護就變成 no-op）。"""
    out = clean_markdown("雜訊 正文", _Dropper())
    assert out == "完全不同的內容"
