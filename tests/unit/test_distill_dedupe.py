"""整理去重＋標已收＋精選冪等（真實使用回饋：整理常收進同一條兩則）。

三道防線：解析時同次去重、整理時標既有為「已收」、精選路由冪等（已在核心理解→不重複新增）。
離線 stub 後端、零外呼可測（教訓 1）。
"""

import unittest

from fastapi.testclient import TestClient

from knowfield.chat.capture import norm_claim
from knowfield.chat.field_chat import FieldChat, _parse_candidates
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_H = [{"role": "user", "content": "為什麼殘差要用加法"},
      {"role": "assistant", "content": "因為加法讓梯度直通。"}]


class StubDistill:
    """reply 回固定蒸餾文字（可含重複主張）。"""
    def __init__(self, text):
        self.text = text

    def reply(self, messages):
        return self.text


class TestNormClaim(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(norm_claim("  殘差  用加法 "), norm_claim("殘差 用加法"))
        self.assertEqual(norm_claim("ReLU"), norm_claim("relu"))


class TestParseDedup(unittest.TestCase):
    def test_same_claim_once(self):                 # 同一次整理內重複主張→只留一條
        text = ("主張：殘差用加法讓梯度直通\n類型：能推導/證明\n"
                "主張：殘差用加法讓梯度直通\n類型：觀察到的規律\n"
                "主張：另一條不同的重點")
        cands = _parse_candidates(text)
        claims = [c.claim for c in cands]
        self.assertEqual(len(cands), 2)
        self.assertIn("殘差用加法讓梯度直通", claims)
        self.assertIn("另一條不同的重點", claims)


class TestDistillMarksAlready(unittest.TestCase):
    def test_existing_root_marked(self):            # 已在核心理解的候選→already=True
        from types import SimpleNamespace
        roots = [SimpleNamespace(claim="殘差用加法讓梯度直通")]
        fc = FieldChat(StubDistill("主張：殘差用加法讓梯度直通\n主張：全新的一條"))
        cands = fc.distill(_H, roots)
        by = {c.claim: c.already for c in cands}
        self.assertTrue(by["殘差用加法讓梯度直通"])     # 已收→標記
        self.assertFalse(by["全新的一條"])              # 新的→不標

if __name__ == "__main__":
    unittest.main()
