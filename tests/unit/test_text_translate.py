"""英→繁翻譯的核心邏輯（spec 038）。零外呼——backend 注入。

⚠️ 與第一刀（簡→繁）最大的差別：翻譯是**生成式**的，模型不保證照規則。
所以「保護片段不完整就整塊退回原文」是必要條件，不是防禦性加碼。
"""
import pytest

from knowfield.text import protect, translate

_MATHY = "Given $x_0 \\sim q(x)$ we define $\\beta_t$ over $T$ steps."


def _good_backend(masked: str) -> str:
    """乖乖照抄佔位符的模型。"""
    return "已翻譯：" + masked


def _drops_placeholder(masked: str) -> str:
    """把佔位符弄丟的模型——生成式模型真的會這樣。"""
    import re
    return re.sub(r"@@KFPROTECT\d+@@", "（公式）", masked)


def _raises(masked: str) -> str:
    raise RuntimeError("後端炸了")


class TestProtectedSegmentIntegrity:
    """US4：保護片段不完整 → 整塊退回原文，不修補。"""

    def test_good_backend_keeps_segments(self):
        r = translate.translate_one(_MATHY, _good_backend)
        assert r.ok is True
        for seg in protect.mask(_MATHY)[1]:
            assert seg in r.text

    def test_dropped_placeholder_falls_back_to_source(self):
        r = translate.translate_one(_MATHY, _drops_placeholder)
        assert r.ok is False
        assert r.text == _MATHY, "保護片段不完整時必須逐字退回原文，不得輸出殘缺譯文"

    def test_no_patching_attempted(self):
        """不嘗試把缺的片段接回去——位置錯的公式比沒翻更糟。"""
        r = translate.translate_one(_MATHY, _drops_placeholder)
        assert "（公式）" not in r.text

    def test_backend_exception_falls_back(self):
        r = translate.translate_one(_MATHY, _raises)
        assert r.ok is False and r.text == _MATHY

    def test_chunk_without_protected_segments(self):
        r = translate.translate_one("Plain prose with no math.", _good_backend)
        assert r.ok is True and r.text.startswith("已翻譯：")


class TestParallelAggregate:
    """US2：並行不得改變塊數與順序。"""

    def test_count_and_order_preserved(self):
        chunks = [f"chunk {i} with $x_{i}$" for i in range(12)]
        out = translate.translate_chunks(chunks, _good_backend, max_workers=8)
        assert len(out) == len(chunks)
        for i, r in enumerate(out):
            assert f"chunk {i}" in r.text, "順序被打亂了"
            assert r.index == i

    def test_one_failure_does_not_affect_others(self):
        chunks = ["a $x$", "b $y$", "c $z$"]
        calls = {"n": 0}

        def flaky(masked):
            calls["n"] += 1
            if "b " in masked:
                raise RuntimeError("只有這塊壞")
            return "T:" + masked

        out = translate.translate_chunks(chunks, flaky, max_workers=4)
        assert [r.ok for r in out] == [True, False, True]
        assert out[1].text == "b $y$", "失敗的塊要逐字退回原文"

    def test_empty_input(self):
        assert translate.translate_chunks([], _good_backend) == []

    def test_single_chunk_does_not_open_pool(self):
        out = translate.translate_chunks(["only $x$"], _good_backend)
        assert len(out) == 1 and out[0].ok is True

    def test_no_backend_returns_source_unchanged(self):
        """後端不可用（None）→ 全部原樣回，不中斷（FR-010）。"""
        chunks = ["a $x$", "b $y$"]
        out = translate.translate_chunks(chunks, None)
        assert [r.text for r in out] == chunks
        assert all(r.ok is False for r in out)


class TestProgress:
    """US2：每完成一塊要能回報（FR-003）。"""

    def test_progress_callback_fires_per_chunk(self):
        chunks = [f"c{i}" for i in range(5)]
        seen = []
        translate.translate_chunks(chunks, _good_backend, max_workers=2,
                                   on_progress=lambda d, t, f: seen.append((d, t, f)))
        assert len(seen) == 5
        assert seen[-1][0] == 5 and seen[-1][1] == 5
        assert [s[0] for s in seen] == sorted(s[0] for s in seen), "done 必須單調遞增"


class TestStreamingProgress:
    """FR-003：進度必須在工作**進行中**吐出。

    ⚠️ 這組測試是重寫的。前兩版都隔著 TestClient 驗，而它會緩衝——我拿一個故意做成
    「全部翻完才吐」的實作去撞，照樣全綠。**一條撞不倒錯誤實作的測試等於沒有測試**。
    改成直接測產生器，時機就驗得到了。
    """

    def test_stage_yielded_before_work_finishes(self):
        import threading
        gate = threading.Event()
        n, lock = {"i": 0}, threading.Lock()

        def staged(masked):
            with lock:
                n["i"] += 1
                mine = n["i"]
            if mine > 1:
                gate.wait(timeout=10)
            return "T:" + masked

        chunks = [f"c{i} $x_{i}$" for i in range(6)]
        gen = translate.translate_stream(chunks, staged, max_workers=6)

        # ⚠️ 關鍵是**時機**不是內容：累積式實作在 gate 逾時（10s）後照樣會吐出
        # 一模一樣的 stage/done=1，所以只斷言內容抓不到它。要有時間上界。
        box = {}
        th = threading.Thread(target=lambda: box.setdefault("first", next(gen)), daemon=True)
        th.start()
        th.join(timeout=2.0)       # 5/6 塊仍卡著；即時實作早該吐了
        assert "first" in box, (
            "2 秒內拿不到第一個進度事件——實作是等全部翻完才吐（假 spinner）")
        first = box["first"]
        assert first[0] == "stage", "第一塊完成時就該吐進度，不能等全部翻完"
        assert first[1]["done"] == 1 and first[1]["total"] == 6
        gate.set()
        rest = list(gen)
        assert rest[-1][0] == "done"
        assert rest[-1][1]["total"] == 6
        assert len(rest[-1][1]["chunks"]) == 6

    def test_stage_count_equals_chunk_count(self):
        chunks = [f"c{i}" for i in range(7)]
        evs = list(translate.translate_stream(chunks, _good_backend, max_workers=3))
        stages = [e for e in evs if e[0] == "stage"]
        assert len(stages) == 7
        assert [s[1]["done"] for s in stages] == list(range(1, 8)), "done 必須單調遞增"

    def test_order_preserved_in_done_payload(self):
        chunks = [f"c{i}" for i in range(6)]
        evs = list(translate.translate_stream(chunks, _good_backend, max_workers=6))
        out = evs[-1][1]["chunks"]
        for i, t in enumerate(out):
            assert f"c{i}" in t, "完成順序不定，但結果順序必須與輸入一致"

    def test_no_backend_still_yields_done(self):
        evs = list(translate.translate_stream(["a", "b"], None))
        assert evs[-1][0] == "done"
        assert evs[-1][1]["chunks"] == ["a", "b"]
        assert evs[-1][1]["failed"] == 2


class TestSeamHandling:
    """⚠️ 接縫：獨立翻譯每塊之後不能再用 `stitch_chunks` 拼。

    `stitch_chunks` 靠**精確字串比對**去除塊間 40 字元重疊。但每塊是獨立翻譯的，
    同一段重疊文字在前後塊會翻成不同中文 → 比對失敗 → 兩份都留下 → 接縫出現
    「條件式 Generat … 條件式生成」這種殘影。**真跑才看得到，測試看不到。**

    解法：翻譯**前**就把重疊裁掉，並記下原本的分隔，翻完照原樣接回。
    """

    def test_dedupe_then_rejoin_reproduces_stitch(self):
        from knowfield.ingest.chunk import chunk_markdown, dedupe_for_translate, stitch_chunks
        md = ("Diffusion models are inspired by non-equilibrium thermodynamics. "
              "They define a Markov chain of diffusion steps to slowly add random noise. " * 12)
        chunks = chunk_markdown(md)
        pieces, seps = dedupe_for_translate(chunks)
        rejoined = pieces[0]
        for p, sep in zip(pieces[1:], seps):
            rejoined += sep + p
        assert rejoined == stitch_chunks(chunks), "去重疊後重組必須與 stitch_chunks 逐字相同"

    def test_known_overlap_is_actually_removed(self):
        """裁掉的量必須等於 chunk_markdown 造出來的重疊量。

        ⚠️ 這條的第一版斷言「相鄰片段完全沒有任何共同前後綴」——**太強了**。
        週期性文字（同一句重複 30 次）相鄰片段會**碰巧**共用前後綴，那不是缺陷。
        真正的要求是「已知的那段重疊被裁掉、重組逐字還原」，不是「不准有任何巧合」。
        """
        from knowfield.ingest.chunk import chunk_markdown, dedupe_for_translate, stitch_chunks
        md = ("Diffusion models slowly add random noise to data and then learn to reverse "
              "the diffusion process to construct desired data samples from the noise. " * 15)
        chunks = chunk_markdown(md)
        pieces, seps = dedupe_for_translate(chunks)
        assert len(pieces) == len([c for c in chunks if c.strip()])
        # 裁掉的總量 = 原始塊總長 − 去重疊後總長，且應等於 stitch 省下的量
        raw_total = sum(len(c) for c in chunks if c.strip())
        piece_total = sum(len(p) for p in pieces)
        assert piece_total < raw_total, "有重疊卻沒裁到任何東西"
        assert piece_total + sum(len(s) for s in seps) == len(stitch_chunks(chunks))

    def test_single_and_empty(self):
        from knowfield.ingest.chunk import dedupe_for_translate
        assert dedupe_for_translate([]) == ([], [])
        assert dedupe_for_translate(["only"]) == (["only"], [])


def _assert_no_midword(units, seps):
    """真正的 mid-word ＝ **分隔是空的**、且兩側都是字母數字。

    ⚠️ 這個 helper 是修出來的：初版直接比對 `units[i][-1]` 與 `units[i+1][0]`，
    **忽略了它們之間的分隔**——切在空格處時 `word` | `word` 會被誤判成切在字中間。
    比較兩個東西之前，要先確定中間沒有第三個東西。
    """
    for a, sep, b in zip(units, seps, units[1:]):
        if sep == "" and a and b:
            assert not (a[-1].isalnum() and b[0].isalnum()), \
                f"從單字中間切開了：…{a[-20:]!r} | {b[:20]!r}…"


class TestTranslationUnits:
    """⚠️ 為檢索切的塊不是合法的翻譯單位。

    `chunk_markdown` 會從**單字中間**切開（實測：Lil'Log 那篇 124 個接縫有 **55 個**是），
    對檢索無害（embedding 照樣算），對翻譯致命——"Conditioned Generation" 被切成
    "Conditioned Generat" ＋ "ion"，後者獨立翻譯就變成「**離子**」。

    翻譯單位必須切在**安全邊界**（段落），而且重組要逐字還原。
    """

    def test_units_never_split_mid_word(self):
        from knowfield.text.translate import split_units
        md = ("Diffusion models are inspired by non-equilibrium thermodynamics.\n\n"
              "They define a Markov chain of diffusion steps to slowly add random noise.\n\n"
              "- Conditioned Generation\n\n- Classifier Guided Diffusion\n\n") * 8
        units, seps = split_units(md, target=300)
        _assert_no_midword(units, seps)

    def test_rejoin_is_verbatim(self):
        from knowfield.text.translate import split_units
        md = ("Some paragraph about diffusion.\n\nAnother one with $x_t$ math.\n\n"
              "```python\nprint(1)\n```\n\nAnd a final paragraph.\n") * 6
        units, seps = split_units(md, target=200)
        out = units[0]
        for u, s in zip(units[1:], seps):
            out += s + u
        assert out == md, "重組必須逐字還原原文"

    def test_units_are_not_absurdly_small_or_large(self):
        from knowfield.text.translate import split_units
        md = ("A paragraph of moderate length about diffusion models and noise. " * 3 + "\n\n") * 10
        units, _ = split_units(md, target=400)
        assert all(u.strip() for u in units), "不得產生空單位"
        assert len(units) >= 2, "夠長的文件應該被切開"

    def test_single_paragraph_stays_one_unit(self):
        from knowfield.text.translate import split_units
        md = "One short paragraph only."
        units, seps = split_units(md, target=400)
        assert units == [md] and seps == []

    def test_oversized_paragraph_is_not_split_mid_word(self):
        """單一段落超過 target 時也不能從字中間切。"""
        from knowfield.text.translate import split_units
        md = "word " * 400          # 一個 2000 字元的段落
        units, seps = split_units(md, target=300)
        _assert_no_midword(units, seps)
        out = units[0]
        for u, s in zip(units[1:], seps):
            out += s + u
        assert out == md


class TestUnitMerging:
    """⚠️ `target` 必須雙向作用：切開過大的，**也合併過小的**。

    初版只切不合——Lil'Log 那篇的清單項（「- 簡化」）每個自成一單位，
    125 塊變成 **211 單位**，API 呼叫數暴增、翻譯從 93s 變 137s，**打破 SC-002**。
    修一個接縫問題卻讓效能退步，是因為 `target` 只管了一半。
    """

    def test_small_paragraphs_are_merged(self):
        from knowfield.text.translate import split_units
        md = "\n\n".join(f"- item {i}" for i in range(40))     # 40 個很短的清單項
        units, seps = split_units(md, target=400)
        assert len(units) < 15, f"沒有合併小段落：{len(units)} 個單位"
        rejoined = units[0]
        for u, s in zip(units[1:], seps):
            rejoined += s + u
        assert rejoined == md

    def test_merged_units_respect_target(self):
        from knowfield.text.translate import split_units
        md = "\n\n".join("x" * 80 for _ in range(30))
        units, _ = split_units(md, target=400)
        for u in units:
            assert len(u) <= 400 * 2, f"合併過頭：{len(u)} 字元"

    def test_merging_still_never_splits_mid_word(self):
        from knowfield.text.translate import split_units
        md = ("Conditioned Generation and Classifier Guided Diffusion methods. " * 5 + "\n\n") * 8
        units, seps = split_units(md, target=500)
        _assert_no_midword(units, seps)

    def test_real_source_unit_count_drops(self):
        """對真實語料：段落切法不該讓單位數比檢索切法還多。"""
        import re as _re
        import sqlite3
        from knowfield.ingest.chunk import stitch_chunks
        from knowfield.text.translate import split_units
        c = sqlite3.connect("knowfield.db")
        raw = [b or "" for (b,) in c.execute(
            "select article_body from digest_entries where url like '%lilianweng%' order by id")]
        if not raw:
            import pytest
            pytest.skip("本機語料沒有這篇")
        md = _re.sub(r"<!--kf-page:\d+-->", "", stitch_chunks(raw))
        units, _ = split_units(md, target=600)
        assert len(units) < 125, f"單位數 {len(units)} 不該多於檢索切出的 125 塊"


class TestContentKey:
    """spec 039 T002：快取以**原文內容**的雜湊判新舊（不用時間戳）。"""

    def test_same_text_same_key(self):
        assert translate.content_key("hello world") == translate.content_key("hello world")

    def test_one_char_differs_key_differs(self):
        # SC-004「0% 機率拿到舊譯文」靠的就是這個——內容動一個字就對不上
        assert translate.content_key("hello world") != translate.content_key("hello worle")

    def test_key_is_hex_digest(self):
        k = translate.content_key("x")
        assert len(k) == 64 and all(c in "0123456789abcdef" for c in k)
