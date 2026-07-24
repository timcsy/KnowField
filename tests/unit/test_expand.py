"""T003 [US1]：QueryExpander——stub 確定性、OpenAI 解析/上限/失敗退回。零外部呼叫。"""

import unittest

from learnnews.search.expand import OpenAIQueryExpander, StubQueryExpander


class TestQueryExpander(unittest.TestCase):
    def test_stub_deterministic_nonempty(self):
        rs = StubQueryExpander().expand("agent 記憶")
        self.assertTrue(len(rs) >= 1)
        self.assertTrue(all(isinstance(s, str) and s.strip() for s in rs))
        self.assertEqual(rs, StubQueryExpander().expand("agent 記憶"))   # 確定性

    def test_openai_parses_lines_and_caps(self):
        def poster(base, path, key, payload):
            content = "子查詢一\n2. 子查詢二\n- 子查詢三\n子查詢四\n子查詢五\n子查詢六"
            return {"choices": [{"message": {"content": content}}]}
        exp = OpenAIQueryExpander("http://x", "k", "m", max_n=5, poster=poster)
        rs = exp.expand("原題")
        self.assertEqual(len(rs), 5)                       # 上限裁切
        self.assertIn("子查詢一", rs)
        self.assertTrue(all(not s[0].isdigit() and not s.startswith("-") for s in rs))  # 去序號/符號

    def test_openai_empty_or_error_returns_empty(self):
        exp_empty = OpenAIQueryExpander("http://x", "k", "m",
                                        poster=lambda *a: {"choices": [{"message": {"content": "   "}}]})
        self.assertEqual(exp_empty.expand("q"), [])

        def boom(*a):
            raise RuntimeError("拆解服務炸了")
        exp_err = OpenAIQueryExpander("http://x", "k", "m", poster=boom)
        self.assertEqual(exp_err.expand("q"), [])          # 不拋、回 []


if __name__ == "__main__":
    unittest.main()
