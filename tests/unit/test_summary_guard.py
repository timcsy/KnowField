"""T023：摘要長度守衛（SC-004、FR-004/005）。"""

import unittest

from learnnews.summarize.summarizer import (
    SummaryBuilder,
    count_sentences,
    first_sentence,
)
from learnnews.summarize.llm import Summarizer
from tests.helpers import make_item


class ChattyBackend:
    """故意回傳多句、像在做分析的後端，用來驗證程式端守衛會截斷。"""

    def summarize(self, title, abstract, matched_topic):
        positioning = "這是一則新聞。它其實非常重要。而且改變一切。"
        why = "值得看。因為我覺得它會顛覆產業。第三句多餘。"
        return positioning, why


class TestSummaryGuard(unittest.TestCase):
    def test_first_sentence(self):
        self.assertEqual(first_sentence("甲。乙。丙"), "甲")

    def test_guard_caps_two_sentences(self):
        item = make_item("測試標題", external_id="1")
        item.id = 1
        s = SummaryBuilder(backend=ChattyBackend()).build(item, "agent")
        self.assertLessEqual(count_sentences(s.text()), 2)
        # 各欄位被截為單句
        self.assertEqual(count_sentences(s.positioning), 1)
        self.assertEqual(count_sentences(s.why_worth), 1)

    def test_stub_backend_default(self):
        item = make_item("關於 LLM 推理", external_id="1")
        item.id = 1
        s = SummaryBuilder().build(item, "LLM 推理")
        self.assertIn("LLM 推理", s.why_worth)
        self.assertLessEqual(count_sentences(s.text()), 2)


if __name__ == "__main__":
    unittest.main()
