"""T012：TTL 快取命中/過期。"""

import unittest

from knowfield.web.cache import TTLCache, normalize_topic


class TestWebCache(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_topic("  Agent  Planning "), "agent planning")

    def test_miss_then_hit(self):
        c = TTLCache(ttl_seconds=100, clock=lambda: 0.0)
        self.assertIsNone(c.get("agent"))
        c.set("agent", "R")
        self.assertEqual(c.get("agent"), "R")

    def test_normalized_key(self):
        c = TTLCache(ttl_seconds=100, clock=lambda: 0.0)
        c.set("Agent", "R")
        self.assertEqual(c.get("  agent "), "R")   # 正規化後同鍵

    def test_expiry(self):
        t = {"now": 0.0}
        c = TTLCache(ttl_seconds=10, clock=lambda: t["now"])
        c.set("agent", "R")
        t["now"] = 5
        self.assertEqual(c.get("agent"), "R")   # 未過期
        t["now"] = 20
        self.assertIsNone(c.get("agent"))        # 已過期


if __name__ == "__main__":
    unittest.main()
