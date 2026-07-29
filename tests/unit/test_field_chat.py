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
        # 膜指令關鍵詞
        for kw in ("grounded", "猜", "derived", "empirical", "applied", "過度抽象", "場-增量", "冊封"):
            self.assertIn(kw, p)

    def test_empty_field_noted(self):                            # T001
        p = build_field_system_prompt([])
        self.assertTrue("場還空" in p or "未接場" in p)


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
    def test_distill_to_candidate(self):                         # T005
        block = ("主張：X 是被 Y 約束逼定\n階梯：\n- 因為 A\n- 所以 B\n"
                 "佐證：https://a/1, https://b/2")
        fc = FieldChat(_SpyBackend(reply=block))
        cand = fc.distill([{"role": "user", "content": "聊了很多"}], [])
        self.assertIsInstance(cand, CandidateDraft)
        self.assertEqual(cand.claim, "X 是被 Y 約束逼定")
        self.assertIn("因為 A", cand.ladder)
        self.assertIn("https://a/1", cand.evidence_urls)


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
