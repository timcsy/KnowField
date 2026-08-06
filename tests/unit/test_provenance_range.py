"""階段 29 第2階段：核心理解記出處則數範圍——distill 標→精選存→由來精準定位。離線注入。"""

import unittest

from fastapi.testclient import TestClient

from knowfield.chat.field_chat import _parse_candidates
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class TestParseRange(unittest.TestCase):
    def test_range(self):
        c = _parse_candidates("主張：殘差直通\n類型：推論\n出處：3-6\n佐證：")[0]
        self.assertEqual((c.src_from, c.src_to), (3, 6))

    def test_single(self):
        c = _parse_candidates("主張：X\n出處：5")[0]
        self.assertEqual((c.src_from, c.src_to), (5, 5))

    def test_missing_defaults_zero(self):
        c = _parse_candidates("主張：X\n類型：推論")[0]
        self.assertEqual((c.src_from, c.src_to), (0, 0))


class TestRangePersist(unittest.TestCase):
    def test_anoint_saves_range(self):
        db = temp_db()
        TestClient(build_app(db)).post(
            "/api/chat/anoint", json={"claim": "殘差直通", "src_from": 3, "src_to": 6})
        repo = Repository(db)
        w = repo.list_why_nodes("anointed")[0]
        self.assertEqual((w.src_from, w.src_to), (3, 6))
        repo.close()

    def test_api_roots_returns_range(self):
        db = temp_db()
        repo = Repository(db)
        wid = repo.add_why_node("X", [], [], False, 0, "2026", src_from=3, src_to=6)
        repo.anoint_why_node(wid); repo.close()
        w = TestClient(build_app(db)).get("/api/roots").json()["anointed"][0]
        self.assertEqual((w["src_from"], w["src_to"]), (3, 6))


class TestDistillNumbers(unittest.TestCase):
    def test_distill_feeds_numbered_convo(self):     # 對話帶 [n] 則號→AI 能標出處
        from knowfield.chat.field_chat import FieldChat

        seen = {}
        class Stub:
            def reply(self, messages):
                seen["convo"] = messages[-1]["content"]
                return "主張：殘差直通\n類型：推論\n出處：1-2\n佐證："
        cands = FieldChat(Stub()).distill(
            [{"role": "user", "content": "殘差?"}, {"role": "assistant", "content": "加法直通"}], [])
        self.assertIn("[1]", seen["convo"])
        self.assertIn("[2]", seen["convo"])
        self.assertEqual((cands[0].src_from, cands[0].src_to), (1, 2))


if __name__ == "__main__":
    unittest.main()
