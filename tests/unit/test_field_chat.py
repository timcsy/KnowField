"""spec 022：跟你的場聊天——膜 prompt、多輪 reply、distill 候選、chat 後端。

核心價值＝反逢迎的膜 system prompt（讀場＋膜＋分層＋提候選）。全離線、零外部呼叫。
"""

import unittest
from unittest import mock

from knowfield.backends.openai_api import OpenAIError
from knowfield.chat.field_chat import (
    CandidateDraft,
    FieldChat,
    OpenAIChatBackend,
    StubChatBackend,
    build_field_system_prompt,
)
from knowfield.rootcause.extract import WhyNode


def _root(cid, claim, ladder):
    return WhyNode(id=cid, claim=claim, evidence_urls=[], touchstones=[], ladder=ladder,
                   fog_flag=False, status="anointed", source_entry_id=0, created_at="2026-07-29")


class _SpyBackend:
    """記下收到的 messages，回一個可辨識的字串。"""
    def __init__(self, reply="（回應）"):
        self.seen = None
        self._reply = reply

    def reply(self, messages):
        self.seen = messages
        return self._reply


class TestSystemPrompt(unittest.TestCase):
    def test_injects_roots_and_membrane(self):                   # T001
        roots = [_root(1, "注意力是被置換對稱逼出來的", ["置換不變⇒加總", "內容決定⇒加權"])]
        p = build_field_system_prompt(roots)
        # 場脈絡注入
        self.assertIn("注意力是被置換對稱逼出來的", p)
        self.assertIn("內容決定⇒加權", p)
        # 膜行為仍在（但用自然語言表達）
        for kw in ("推測", "類比", "存", "推", "自然"):
            self.assertIn(kw, p)
        # de-jargon：輸出不該用內部術語，且明令不要用
        self.assertIn("不要用內部術語", p)

    def test_empty_field_noted(self):                            # T001
        p = build_field_system_prompt([])
        self.assertTrue("場還空" in p or "未接場" in p or "還空" in p)

    def test_has_brevity_discipline(self):
        """膜必須含長度紀律。實測：沒有這句，同一題 2732 字；有這句 447 字（品質不掉）。

        真因不是「有東西在推長」，是模型預設就話多、而膜從來沒叫它短（`history/092`）。
        """
        p = build_field_system_prompt([_root(1, "某條理解", ["階梯"])])
        self.assertIn("長度紀律", p)
        self.assertIn("精簡", p)
        # 反逢迎的判準是給模型用的，不是拿來逐條演給使用者看（＝回答變長的機制之一）
        self.assertIn("判準", p)


class TestReplyWithSources(unittest.TestCase):
    def test_sources_injected_for_inline_citation(self):         # 每輪撒網→回答可標 [n]
        from knowfield.search.websearch import SearchResult
        spy = _SpyBackend()
        FieldChat(spy).reply([], "問題", [], [SearchResult("標題T", "https://a/1", "摘要S")])
        joined = " ".join(m["content"] for m in spy.seen)
        self.assertIn("https://a/1", joined)                     # 來源進了提示
        self.assertIn("[n]", joined)                             # 有指示標 [n]

    def test_no_sources_no_injection(self):
        spy = _SpyBackend()
        FieldChat(spy).reply([], "問題", [])                     # sources 省略
        # 只有 system(場) + user，無來源 system 段
        self.assertEqual(len(spy.seen), 2)

    def test_max_history_trims(self):                            # 砍歷史省 token（快取友善）
        spy = _SpyBackend()
        hist = [{"role": "user", "content": f"第{i}句"} for i in range(6)]
        FieldChat(spy).reply(hist, "新問題", [], max_history=2)
        # system(場) + 最近 2 則 + user＝4；且舊的「第0句」不在
        self.assertEqual(len(spy.seen), 4)
        joined = " ".join(m["content"] for m in spy.seen)
        self.assertNotIn("第0句", joined)
        self.assertIn("第5句", joined)
        self.assertEqual(spy.seen[0]["role"], "system")          # 場仍在最前（快取前綴）


class _StreamSpy:
    """回固定 reply；stream 把它分兩段吐。"""
    def reply(self, messages):
        self.seen = messages
        return "串流回應 [1]"
    def stream(self, messages):
        self.seen = messages
        yield "串流"
        yield "回應 [1]"


class TestReplyStream(unittest.TestCase):
    def test_reply_stream_yields_tokens(self):
        chunks = list(FieldChat(_StreamSpy()).reply_stream([], "問", [], max_history=0))
        self.assertEqual("".join(chunks), "串流回應 [1]")

    def test_stub_backend_streams(self):
        out = "".join(StubChatBackend().stream([{"role": "user", "content": "嗨"}]))
        self.assertEqual(out, StubChatBackend().reply([{"role": "user", "content": "嗨"}]))


class TestTitle(unittest.TestCase):
    def test_title_from_backend(self):                           # T005
        t = FieldChat(_SpyBackend(reply="注意力為何用加權")).title(
            [{"role": "user", "content": "attention 的本質？"}])
        self.assertEqual(t, "注意力為何用加權")

    def test_title_fallback_on_failure(self):                    # T005（教訓 3）
        class _Boom:
            def reply(self, m): raise RuntimeError("炸")
        t = FieldChat(_Boom()).title([{"role": "user", "content": "這段對話在聊 X 的原理"}])
        self.assertTrue(t.strip())                               # 不崩、有 fallback
        self.assertIn("X", t)                                    # 退回首個 user 訊息


class TestUrlContents(unittest.TestCase):
    def test_url_content_injected(self):                         # 貼的網址內容進提示
        spy = _SpyBackend()
        FieldChat(spy).reply([], "看這篇 https://a/1", [], url_contents=[
            {"url": "https://a/1", "title": "某論文", "body": "這是全文內容 XYZ"}])
        joined = " ".join(m["content"] for m in spy.seen)
        self.assertIn("這是全文內容 XYZ", joined)                # 抓到的內容注入了
        self.assertIn("某論文", joined)

    def test_unfetchable_url_gives_note(self):                   # 抓不到→note、不假裝讀過
        spy = _SpyBackend()
        FieldChat(spy).reply([], "看這 https://blocked/x", [], url_contents=[
            {"url": "https://blocked/x", "title": "", "body": ""}])
        joined = " ".join(m["content"] for m in spy.seen)
        self.assertIn("抓不到", joined)
        self.assertIn("不要假裝讀過", joined)


class TestSearchQuery(unittest.TestCase):
    def test_extracts_query(self):
        q = FieldChat(_SpyBackend(reply="flow matching generative model")).search_query(
            [], "Flow Matching 是什麼？")
        self.assertEqual(q, "flow matching generative model")

    def test_fallback_to_message_on_empty(self):
        q = FieldChat(_SpyBackend(reply="")).search_query([], "原問題")
        self.assertEqual(q, "原問題")


class TestStubBackend(unittest.TestCase):
    def test_deterministic_offline(self):                        # T002
        out = StubChatBackend().reply([{"role": "user", "content": "嗨"}])
        self.assertTrue(out.strip())                             # 有回應、零外部呼叫


class TestFieldChatReply(unittest.TestCase):
    def test_builds_system_history_user(self):                   # T003
        roots = [_root(1, "根因A", ["階梯1"])]
        spy = _SpyBackend()
        fc = FieldChat(spy)
        hist = [{"role": "user", "content": "前一句"},
                {"role": "assistant", "content": "前一答"}]
        fc.reply(hist, "新問題", roots)
        msgs = spy.seen
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("根因A", msgs[0]["content"])               # 場脈絡在 system
        self.assertEqual(msgs[1:3], hist)                        # 歷史保留（多輪）
        self.assertEqual(msgs[-1], {"role": "user", "content": "新問題"})


class TestDistill(unittest.TestCase):
    def test_distill_single(self):                               # T005
        block = ("主張：X 是被 Y 約束逼定\n類型：能推導/證明\n階梯：\n- 因為 A\n- 所以 B\n"
                 "佐證：https://a/1, https://b/2")
        cands = FieldChat(_SpyBackend(reply=block)).distill(
            [{"role": "user", "content": "聊了很多"}], [])
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].claim, "X 是被 Y 約束逼定")
        self.assertEqual(cands[0].kind, "能推導/證明")
        self.assertIn("因為 A", cands[0].ladder)
        self.assertIn("https://a/1", cands[0].evidence_urls)

    def test_distill_multiple_layers(self):                      # 多條、不同層次
        block = ("主張：地基那條\n類型：能推導/證明\n階梯：\n- 因為 A\n\n"
                 "主張：觀察到的那條\n類型：觀察到的規律\n階梯：\n- 觀察 B\n\n"
                 "主張：只是類比那條\n類型：類比/發想")
        cands = FieldChat(_SpyBackend(reply=block)).distill([{"role": "user", "content": "x"}], [])
        self.assertEqual(len(cands), 3)
        self.assertEqual([c.kind for c in cands],
                         ["能推導/證明", "觀察到的規律", "類比/發想"])
        self.assertEqual(cands[2].claim, "只是類比那條")


class TestOpenAIChatBackend(unittest.TestCase):
    def test_calls_chat(self):                                   # T006
        seen = {}

        def poster(base, path, key, payload):
            seen["path"] = path
            seen["n"] = len(payload["messages"])
            return {"choices": [{"message": {"content": "（真後端回應）"}}]}
        out = OpenAIChatBackend("b", "k", "m", poster=poster).reply(
            [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}])
        self.assertEqual(out, "（真後端回應）")
        self.assertEqual(seen["path"], "/chat/completions")
        self.assertEqual(seen["n"], 2)

    def test_poster_failure_raises(self):                        # T006（教訓 3）
        def boom(*a, **k):
            raise RuntimeError("網路炸了")
        with self.assertRaises(OpenAIError):
            OpenAIChatBackend("b", "k", "m", poster=boom).reply([{"role": "user", "content": "u"}])


if __name__ == "__main__":
    unittest.main()


def _drain(gen):
    """把 generator 吐完，回 (chunks, return 值)——截斷原因走 generator 的回傳值傳上來。"""
    out = []
    while True:
        try:
            out.append(next(gen))
        except StopIteration as stop:
            return out, (stop.value or "")


class TestTruncationVisible(unittest.TestCase):
    """截斷要看得見（憲章 V）：finish_reason 一路傳到呼叫端；中途斷線統一成 OpenAIError。

    兩種截斷（撞上限／連線斷）在畫面上長得一模一樣，分不出來就會像上次那樣只治到一種。
    """

    def test_backend_stream_propagates_finish_reason(self):
        def streamer(base, path, key, payload, **kw):
            yield "半句"
            return "length"
        chunks, reason = _drain(OpenAIChatBackend("b", "k", "m", streamer=streamer).stream(
            [{"role": "user", "content": "u"}]))
        self.assertEqual(chunks, ["半句"])
        self.assertEqual(reason, "length")                        # 撞 max_tokens 被切

    def test_field_chat_propagates_finish_reason(self):
        class _Cut:
            def stream(self, messages):
                yield "半"
                return "length"
        _, reason = _drain(FieldChat(_Cut()).reply_stream([], "問", []))
        self.assertEqual(reason, "length")                        # 穿過 FieldChat 不掉

    def test_normal_finish_has_no_truncation(self):
        _, reason = _drain(FieldChat(_StreamSpy()).reply_stream([], "問", []))
        self.assertEqual(reason, "")                              # 正常講完＝不標截斷


class TestPostStreamRobust(unittest.TestCase):
    """`_post_stream` 的兩個洞：finish_reason 沒讀、迭代不在 try 內。"""

    @staticmethod
    def _resp(lines):
        class _R:
            def __iter__(self):
                yield from lines
        return _R()

    def test_reads_finish_reason_length(self):
        from knowfield.backends import openai_api as oa
        lines = [b'data: {"choices":[{"delta":{"content":"\xe5\x8d\x8a\xe5\x8f\xa5"}}]}\n',
                 b'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n',
                 b'data: [DONE]\n']
        with mock.patch.object(oa.urllib.request, "urlopen", return_value=self._resp(lines)):
            chunks, reason = _drain(oa._post_stream("http://x", "/p", "k", {}))
        self.assertEqual(chunks, ["半句"])
        self.assertEqual(reason, "length")

    def test_midstream_break_becomes_openai_error(self):
        """迭代途中斷線＝目前在 try 外面、會裸奔穿出去（教訓：邊界要攔所有失敗，不只一種）。"""
        from knowfield.backends import openai_api as oa

        class _Boom:
            def __iter__(self):
                yield b'data: {"choices":[{"delta":{"content":"\xe5\x8d\x8a"}}]}\n'
                raise ConnectionResetError("連線被切")
        with mock.patch.object(oa.urllib.request, "urlopen", return_value=_Boom()):
            gen = oa._post_stream("http://x", "/p", "k", {})
            self.assertEqual(next(gen), "半")
            with self.assertRaises(OpenAIError):
                next(gen)


class TestBareMode(unittest.TestCase):
    """bare＝這輪暫時屏蔽知識庫：不注入核心理解，但反逢迎人格仍在。"""

    def test_bare_skips_knowledge_field(self):
        spy = _SpyBackend()
        roots = [_root(1, "注意力是被置換對稱逼出來的", ["置換不變⇒加總"])]
        FieldChat(spy).reply([], "隨便問", roots, bare=True)
        sysmsg = spy.seen[0]["content"]
        self.assertNotIn("注意力是被置換對稱逼出來的", sysmsg)   # 知識庫沒被注入
        self.assertIn("屏蔽", sysmsg)                          # 有說明這輪不接知識庫
        self.assertIn("好聽話", sysmsg)                        # 反逢迎人格（膜）仍在
        self.assertIn("長度紀律", sysmsg)                      # bare 走另一條路，長度紀律別漏掉

    def test_non_bare_still_injects(self):
        spy = _SpyBackend()
        roots = [_root(1, "注意力是被置換對稱逼出來的", ["置換不變⇒加總"])]
        FieldChat(spy).reply([], "隨便問", roots, bare=False)
        self.assertIn("注意力是被置換對稱逼出來的", spy.seen[0]["content"])
