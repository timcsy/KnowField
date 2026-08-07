"""核心理解的認識論層次（kind）：distill 看上下文判→持久化→顯示→聊天用。
4 檔：已證實／推論／類比／猜想（draft 2026-08-06、vision 階段 28）。離線注入、零外呼。"""

import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class TestKindPersist(unittest.TestCase):
    def test_add_and_list_kind(self):                      # 精選後不再丟失層級
        db = temp_db()
        repo = Repository(db)
        wid = repo.add_why_node("殘差直通", [], [], False, 0, "2026", ladder=["a"], kind="推論")
        repo.anoint_why_node(wid)
        self.assertEqual(repo.list_why_nodes("anointed")[0].kind, "推論")
        repo.close()

    def test_default_kind_empty(self):                     # 沒標→空、不崩
        db = temp_db()
        repo = Repository(db)
        repo.add_why_node("x", [], [], False, 0, "2026")
        self.assertEqual(repo.list_why_nodes()[0].kind, "")
        repo.close()


class TestKindMigration(unittest.TestCase):
    def test_row_without_kind_reads_empty(self):           # 沒帶 kind 的舊列→讀成 ""、不崩
        # spec 034：SQLite 的 _migrate 補欄已移除（PG 從零起、schema 已含 kind、default ''）。
        # 保留 parity 意圖：不帶 kind 插入的「舊式」列，讀出 kind="" 且不崩。
        db = temp_db()
        repo = Repository(db)
        repo.conn.execute("INSERT INTO why_nodes (claim, status) VALUES ('舊條','anointed')")
        repo.conn.commit()
        self.assertEqual(repo.list_why_nodes("anointed")[0].kind, "")
        repo.close()


class TestDistillKind(unittest.TestCase):
    def test_parse_kind(self):
        from knowfield.chat.field_chat import _parse_candidates
        c = _parse_candidates("主張：殘差用加法讓梯度直通\n類型：推論\n階梯：\n- 加法不擋梯度\n佐證：")[0]
        self.assertEqual(c.kind, "推論")

    def test_distill_prompt_has_four_categories(self):     # 對齊 4 檔
        from knowfield.chat.field_chat import _DISTILL
        for k in ["已證實", "推論", "類比", "猜想"]:
            self.assertIn(k, _DISTILL)


class TestAnointKind(unittest.TestCase):
    def test_api_anoint_saves_kind(self):                  # 聊天精選帶層級
        db = temp_db()
        TestClient(build_app(db)).post(
            "/api/chat/anoint", json={"claim": "殘差直通", "kind": "推論"})
        repo = Repository(db)
        self.assertEqual(repo.list_why_nodes("anointed")[0].kind, "推論")
        repo.close()

    def test_whynode_anoint_sets_kind(self):               # 來源候選在來源頁精選時選層級
        db = temp_db()
        repo = Repository(db)
        wid = repo.add_why_node("來源蒸餾的候選", ["http://x"], [], False, 0, "2026")  # kind 空
        repo.close()
        TestClient(build_app(db)).post(
            "/api/whynode/anoint", json={"id": wid, "kind": "類比"})
        repo = Repository(db)
        w = repo.list_why_nodes("anointed")[0]
        self.assertEqual(w.kind, "類比")
        repo.close()


class TestRootsKind(unittest.TestCase):
    def test_api_roots_returns_kind(self):
        db = temp_db()
        repo = Repository(db)
        wid = repo.add_why_node("x", [], [], False, 0, "2026", kind="類比")
        repo.anoint_why_node(wid); repo.close()
        r = TestClient(build_app(db)).get("/api/roots").json()
        self.assertEqual(r["anointed"][0]["kind"], "類比")


class TestPromptKind(unittest.TestCase):
    def test_system_prompt_shows_kind(self):               # 聊天時 AI 看得到層級
        from types import SimpleNamespace

        from knowfield.chat.field_chat import build_field_system_prompt
        p = build_field_system_prompt(   # claim 不含層級詞→「猜想」只能來自 kind
            [SimpleNamespace(claim="殘差用加法讓梯度直通", ladder=["a"], kind="猜想")])
        self.assertIn("猜想", p)


if __name__ == "__main__":
    unittest.main()
