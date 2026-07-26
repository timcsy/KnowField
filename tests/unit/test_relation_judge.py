"""T004 [US1]：RelationJudge——stub 確定性、OpenAI 解析/牴觸/失敗。零外部呼叫。"""

import json
import unittest

from learnnews.field.relate import OpenAIRelationJudge, StubRelationJudge
from learnnews.sources.base import SourceUnavailable


class TestRelationJudge(unittest.TestCase):
    def test_stub_deterministic(self):
        r = StubRelationJudge().judge("材料標題", "材料內文", "根因主張")
        self.assertIn(r["kind"], ("extend", "contradict", "none"))
        self.assertTrue(r["reason"])

    def test_openai_parses_contradict(self):
        def poster(base, path, key, body):
            return {"choices": [{"message": {"content": json.dumps(
                {"kind": "contradict", "reason": "材料的結論與此根因相反"}, ensure_ascii=False)}}]}
        r = OpenAIRelationJudge("http://x", "k", "m", poster=poster).judge("t", "b", "根因")
        self.assertEqual(r["kind"], "contradict")             # 牴觸解析對
        self.assertIn("相反", r["reason"])

    def test_openai_failure_raises(self):
        def boom(*a):
            raise RuntimeError("判關係服務炸了")
        with self.assertRaises(SourceUnavailable):
            OpenAIRelationJudge("http://x", "k", "m", poster=boom).judge("t", "b", "根因")


if __name__ == "__main__":
    unittest.main()
