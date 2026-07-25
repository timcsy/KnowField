"""_canonical 對混合時區的 published_at 不得炸（治重整失敗：naive vs aware）。"""

import unittest
from datetime import datetime, timezone

from learnnews.digest.builder import DigestBuilder
from learnnews.models import Item


def _item(title, url, dt):
    return Item(source_id="s", external_id="", title=title, url=url,
                abstract="x", published_at=dt)


class TestCanonicalTz(unittest.TestCase):
    def test_mixed_aware_naive_does_not_crash(self):
        group = [
            _item("A", "https://a/1", datetime(2026, 7, 25, tzinfo=timezone.utc)),  # aware
            _item("B", "https://a/2", datetime(2026, 7, 24)),                        # naive
            _item("C", "https://a/3", None),                                         # None
        ]
        rep = DigestBuilder._canonical(group)                 # 不拋 TypeError
        self.assertIsNotNone(rep)
        # 最早的是 naive 的 2026-07-24（B）——正規化後可比
        self.assertEqual(rep.title, "B")

    def test_all_none(self):
        group = [_item("A", "https://a/1", None), _item("B", "https://a/2", None)]
        self.assertIsNotNone(DigestBuilder._canonical(group))


if __name__ == "__main__":
    unittest.main()
