"""spec 022：跟你的場聊天——膜 prompt、多輪 reply、distill 候選、chat 後端。

核心價值＝反逢迎的膜 system prompt（讀場＋膜＋分層＋提候選）。全離線、零外部呼叫。
"""

import unittest

from learnnews.backends.openai_api import OpenAIError
from learnnews.chat.field_chat import (
    CandidateDraft,
    FieldChat,
    OpenAIChatBackend,
    StubChatBackend,
    build_field_system_prompt,
)
from learnnews.rootcause.extract import WhyNode


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


class TestReplyWithSources(unittest.TestCase):
    def test_sources_injected_for_inline_citation(self):         # 每輪撒網→回答可標 [n]
        from learnnews.search.websearch import SearchResult
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
