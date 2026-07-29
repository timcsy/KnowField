"""spec 025：收料純核心——內容指紋（去重識別）＋收尾缺口判準。離線、缺項不崩。"""

import unittest

from learnnews.chat.capture import conversation_fingerprint, distill_gap


class TestFingerprint(unittest.TestCase):
    def test_same_content_same_fp(self):                    # T002
        m = [{"role": "user", "content": "q"},
             {"role": "assistant", "content": "a"}]
        self.assertEqual(conversation_fingerprint(m), conversation_fingerprint(list(m)))

    def test_different_content_differ(self):                # T002
        a = [{"role": "user", "content": "q1"}]
        b = [{"role": "user", "content": "q2"}]
        self.assertNotEqual(conversation_fingerprint(a), conversation_fingerprint(b))

    def test_order_matters(self):                           # T002
        a = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]
        b = [{"role": "assistant", "content": "y"}, {"role": "user", "content": "x"}]
        self.assertNotEqual(conversation_fingerprint(a), conversation_fingerprint(b))

    def test_empty_stable(self):                            # T002
        self.assertEqual(conversation_fingerprint([]), conversation_fingerprint([]))
        self.assertIsInstance(conversation_fingerprint([]), str)

    def test_missing_content_ok(self):                      # T002 缺欄位不崩
        fp = conversation_fingerprint([{"role": "assistant"}])
        self.assertIsInstance(fp, str)

    def test_ignores_sources(self):                         # T002 忽略易變欄
        a = [{"role": "assistant", "content": "a", "sources": [{"url": "u1"}]}]
        b = [{"role": "assistant", "content": "a", "sources": [{"url": "u2"}]}]
        self.assertEqual(conversation_fingerprint(a), conversation_fingerprint(b))


class TestDistillGap(unittest.TestCase):
    # 用 min_total=8、gap=6 做例（實作可用不同預設；這裡顯式傳參）
    def test_long_and_uncaptured_returns_range(self):       # T003
        self.assertEqual(distill_gap(20, 4, 8, 6), (5, 20))

    def test_short_none(self):                              # T003 太短不吵
        self.assertIsNone(distill_gap(5, 0, 8, 6))

    def test_just_captured_none(self):                      # T003 剛收滿→缺口不足
        self.assertIsNone(distill_gap(20, 18, 8, 6))

    def test_gap_exactly_threshold(self):                   # T003 邊界：等於門檻→提醒
        self.assertEqual(distill_gap(14, 8, 8, 6), (9, 14))

    def test_last_captured_none_or_negative_as_zero(self):  # T003
        self.assertEqual(distill_gap(10, None, 8, 6), (1, 10))
        self.assertEqual(distill_gap(10, -3, 8, 6), (1, 10))

    def test_nonpositive_total_none(self):                  # T003
        self.assertIsNone(distill_gap(0, 0, 8, 6))
        self.assertIsNone(distill_gap(-1, 0, 8, 6))


if __name__ == "__main__":
    unittest.main()
