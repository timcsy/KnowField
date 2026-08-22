"""spec 043：釘住這段對話冊封出的核心理解。零外呼——注入 stub embedder 或直接關掉排序。

⚠️ 兩條沉默失效型：
  ① 「不依賴向量檢索」——檢索通常也會選中，所以必須在**排序停用**下驗，否則測到的是巧合。
  ② 「釘住不繞過認識論分層」——把 pinned 直接塞進 body 會讓 `猜想` 進正文，
     而「高證實文章」是這功能的整個賣點。實測 referrers 裡真的有猜想（對話 #20）。
"""
from knowfield.output.article import generate_article


class _Node:
    def __init__(self, i, claim, kind="推論"):
        self.id, self.claim, self.kind = i, claim, kind
        self.status = "anointed"
        self.evidence = ""
        self.source_url = ""


class _Backend:
    """⚠️ 要留住 prompt：正文節點的**主張**只出現在送給模型的 prompt 裡，
    `_references()`（`article.py:65`）渲染的是 URL 或「（你收藏的來源）」，**沒有主張**。
    拿 markdown 驗「這條有沒有進正文」會永遠失敗——這是實作時才發現、並回頭改了規格 SC-001 的地方。"""
    def __init__(self): self.prompt = ""
    def reply(self, messages):
        self.prompt = "\n".join(m["content"] for m in messages)
        return "## 標題\n\n內容一段。"


class _Embedder:
    """把不含 zzz 的排前面——讓「排序會不會蓋掉釘住」變成確定性的。"""
    def embed(self, text): return [1.0, 0.0]
    def embed_many(self, texts):
        return [[0.0, 1.0] if "zzz" in t else [1.0, 0.0] for t in texts]


def _field(n=12):
    return [_Node(100 + i, f"場裡第 {i} 條理解", "推論") for i in range(n)]


def _refs(kinds=("推論", "推論")):
    return [_Node(i, f"zzz 對話冊封的第 {i} 條", k) for i, k in enumerate(kinds)]


def _seen(be, out):
    """模型看得到的 ＋ 使用者看得到的。正文主張在 prompt，延伸閱讀主張在 markdown。"""
    return be.prompt + "\n" + out["markdown"]


class TestPinnedAlwaysConsidered:
    def test_pinned_all_present(self):
        pin = _refs(); be = _Backend()
        out = generate_article("主題", _field() + pin, be, embedder=_Embedder(), pinned=pin)
        for p in pin:
            assert p.claim in _seen(be, out)

    def test_pinned_present_without_embedder(self):
        """⚠️ SC-002：排序停用時仍成立——這才是 FR-002 的真正驗收。"""
        pin = _refs(); be = _Backend()
        out = generate_article("主題", _field() + pin, be, embedder=None, pinned=pin)
        for p in pin:
            assert p.claim in _seen(be, out)

    def test_pinned_survives_hostile_ranking(self):
        """⚠️ embedder 刻意把 pinned（含 zzz）排到最後——釘住必須贏過排序。"""
        pin = _refs(); be = _Backend()
        out = generate_article("主題", _field(20) + pin, be, embedder=_Embedder(), pinned=pin)
        for p in pin:
            assert p.claim in _seen(be, out)


class TestLayeringNotBypassed:
    def test_guess_pinned_goes_to_extended_reading(self):
        """⚠️ SC-003：釘的是「必被考慮」，不是「必進正文」。"""
        pin = _refs(("推論", "猜想"))
        guess = pin[1]; be = _Backend()
        out = generate_article("主題", _field() + pin, be, embedder=None, pinned=pin)
        assert guess.claim not in be.prompt, "猜想被餵進正文的 prompt——高證實的賣點破了"
        md = out["markdown"]
        assert guess.claim in md, "猜想那條整個不見了（該在延伸閱讀）"
        head, _, tail = md.partition("延伸閱讀")
        assert tail, "沒有延伸閱讀區塊"
        assert guess.claim not in head, "猜想被釘進了正文——高證實的賣點破了"


class TestThickness:
    def test_field_tops_up_when_referrers_are_few(self):
        """SC-004：只有 2 條 referrers 時，正文仍要有厚度。"""
        pin = _refs(); be = _Backend()
        generate_article("主題", _field() + pin, be, embedder=None, pinned=pin, top_k=8)
        assert be.prompt.count("場裡第") >= 5


class TestNoRegression:
    def test_without_pinned_is_byte_identical(self):
        """⚠️ SC-005：不給 pinned 時輸出逐字相同。
        ⚠️ 不能寫成 f(pinned=None) == f() ——那是拿同一份程式碼比自己（同義反覆）。
        這裡比對的是**不含任何 pinned 專屬痕跡**、且節點全來自場。"""
        field = _field(); be = _Backend()
        out = generate_article("主題", field, be, embedder=None)
        assert out["empty"] is False
        assert "zzz" not in be.prompt and "zzz" not in out["markdown"]
        assert out["title"] == "主題"
