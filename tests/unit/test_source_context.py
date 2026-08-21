"""spec 042：帶入來源的選段。純函式、零外呼——檢索名次由呼叫端算好傳進來。

⚠️ 這裡最重要的一條是「**沒有任何一段是被硬切的**」。spec 041 對文章用的是 `[:CAP]`，
被丟掉的後半使用者看不見——那是沉默失敗（FR-005 明文禁止在本刀重複）。
"""
import pytest

from knowfield.chat.source_context import select_source_context

_CHUNKS = [f"第 {i} 段的內容。" * 20 for i in range(10)]     # 每段約 200 字


class TestShortSource:
    def test_all_chunks_when_under_cap(self):
        r = select_source_context(_CHUNKS, ranked_idx=[], cap=100_000, head_chars=500)
        assert r.excerpted is False
        assert r.shown_units == r.total_units == 10
        for c in _CHUNKS:
            assert c in r.body


class TestLongSource:
    def test_excerpts_and_declares(self):
        r = select_source_context(_CHUNKS, ranked_idx=[7, 8], cap=900, head_chars=400)
        assert r.excerpted is True
        assert r.total_units == 10
        assert 0 < r.shown_units < 10

    def test_head_is_always_kept(self):
        """沒有開頭就答不出「這篇整體在講什麼」（FR-005）。"""
        r = select_source_context(_CHUNKS, ranked_idx=[9], cap=900, head_chars=400)
        assert _CHUNKS[0] in r.body

    def test_ranked_chunks_are_included(self):
        r = select_source_context(_CHUNKS, ranked_idx=[7], cap=1200, head_chars=400)
        assert _CHUNKS[7] in r.body

    def test_no_chunk_is_cut_in_half(self):
        """⚠️ 本檔的核心斷言：出現在 body 裡的每一段，都與某個原始塊**逐字相等**。
        硬切會讓最後一段變成半句，而使用者永遠不知道少了什麼。"""
        r = select_source_context(_CHUNKS, ranked_idx=[3, 5, 7], cap=1000, head_chars=400)
        parts = [p for p in r.body.split("\n\n") if p and not p.startswith("（")]
        for p in parts:
            assert p in _CHUNKS, f"這一段不是完整的原始塊：{p[:40]}…"

    def test_body_within_cap(self):
        r = select_source_context(_CHUNKS, ranked_idx=list(range(10)), cap=1000, head_chars=400)
        assert len(r.body) <= 1000 + 200          # 容一段的溢出（寧可整段，不切半）


class TestEdges:
    def test_empty(self):
        r = select_source_context([], ranked_idx=[], cap=1000, head_chars=400)
        assert r.body == "" and r.total_units == 0 and r.excerpted is False

    def test_single_huge_chunk_is_not_cut(self):
        """⚠️ 單一超長塊：寧可整塊給、也不切半——切半是沉默失敗。"""
        big = "x" * 5000
        r = select_source_context([big], ranked_idx=[0], cap=1000, head_chars=400)
        assert big in r.body
