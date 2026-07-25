"""T004/T005 [US1]：RootCauseExtractor——stub 確定性、OpenAI 解析/失敗/no_material。零外部呼叫。"""

import json
import unittest

from learnnews.rootcause.extract import Candidate, OpenAIExtractor, StubExtractor
from learnnews.sources.base import SourceUnavailable


class TestExtractor(unittest.TestCase):
    def test_stub_returns_candidate(self):
        c = StubExtractor().extract("Attention 論文", "self-attention 讓每個 token 直接看全序列")
        self.assertIsInstance(c, Candidate)
        self.assertTrue(c.claim.strip())
        self.assertEqual(len(c.touchstones), 7)               # 7 條試金石
        self.assertTrue(all(t["passed"] is False for t in c.touchstones))  # 離線全「待驗」
        self.assertFalse(c.no_material)
        self.assertGreaterEqual(len(c.ladder), 2)             # why 階梯（表面→bedrock）

    def test_openai_parses_ladder(self):
        payload = {"claim": "bedrock aha", "no_material": False,
                   "ladder": ["表面 why", "更深", "bedrock：資訊理論極限"], "touchstones": []}
        import json as _j

        def poster(*a):
            return {"choices": [{"message": {"content": _j.dumps(payload, ensure_ascii=False)}}]}
        c = OpenAIExtractor("http://x", "k", "m", poster=poster).extract("T", "B")
        self.assertEqual(c.ladder, ["表面 why", "更深", "bedrock：資訊理論極限"])
        self.assertEqual(c.claim, "bedrock aha")

    def test_openai_parses_json(self):
        payload = {"claim": "因為直接建模長程依賴", "no_material": False, "fog_flag": True,
                   "touchstones": [{"name": "預測力", "passed": True},
                                   {"name": "機制", "passed": False}]}

        def poster(base, path, key, body):
            return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}
        c = OpenAIExtractor("http://x", "k", "m", poster=poster).extract("T", "B")
        self.assertEqual(c.claim, "因為直接建模長程依賴")
        self.assertTrue(c.fog_flag)
        self.assertEqual(len(c.touchstones), 2)
        self.assertEqual(c.evidence, [])                      # evidence 由呼叫端補（種子 url）

    def test_openai_no_material(self):
        def poster(*a):
            return {"choices": [{"message": {"content": '{"no_material": true, "claim": ""}'}}]}
        c = OpenAIExtractor("http://x", "k", "m", poster=poster).extract("T", "B")
        self.assertTrue(c.no_material)

    def test_openai_failure_raises(self):
        def boom(*a):
            raise RuntimeError("萃取服務炸了")
        with self.assertRaises(SourceUnavailable):
            OpenAIExtractor("http://x", "k", "m", poster=boom).extract("T", "B")


if __name__ == "__main__":
    unittest.main()
