"""每來源上限：單一來源不得洗版匯整（治「都是 OpenAI」）。"""

import unittest
from dataclasses import dataclass

from learnnews.digest.builder import _cap_per_source


@dataclass
class _S:
    source_id: str
    n: int


class _Item:
    def __init__(self, sid, n): self.source_id = sid; self.n = n


class _Scored:
    def __init__(self, sid, n): self.item = _Item(sid, n)


class TestCapPerSource(unittest.TestCase):
    def test_caps_each_source_preserving_order(self):
        scored = [_Scored("openai", i) for i in range(13)] + \
                 [_Scored("arxiv", 0), _Scored("reddit", 0)]
        out = _cap_per_source(scored, 3)
        sids = [s.item.source_id for s in out]
        self.assertEqual(sids.count("openai"), 3)             # OpenAI 上限 3
        self.assertEqual(sids.count("arxiv"), 1)
        self.assertEqual(sids.count("reddit"), 1)
        # 保序：前 3 個 openai 是原本前 3（rank 順）
        self.assertEqual([s.item.n for s in out if s.item.source_id == "openai"], [0, 1, 2])

    def test_none_or_zero_means_no_cap(self):
        scored = [_Scored("x", i) for i in range(5)]
        self.assertEqual(len(_cap_per_source(scored, None)), 5)
        self.assertEqual(len(_cap_per_source(scored, 0)), 5)


if __name__ == "__main__":
    unittest.main()
