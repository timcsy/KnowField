"""spec 024：NotebookLM 匯出端點——text/plain、md/urls、404、唯讀守衛（原則 6）。"""

import json
import unittest

from fastapi.testclient import TestClient

from learnnews.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_HIST = [
    {"role": "user", "content": "attention 為何加權？"},
    {"role": "assistant", "content": "內容決定權重 [1]，殘差累加 [2]。",
     "sources": [{"n": 1, "url": "https://a/1", "title": "Attention"},
                 {"n": 2, "url": "https://a/2", "title": "殘差"}]},
]


def _now():
    return "2026-07-29T00:00:00Z"


class TestChatExport(unittest.TestCase):
    def test_chat_export_md(self):                          # T005
        app = build_app(temp_db())
        r = TestClient(app).post("/chat/export", data={
            "history": json.dumps(_HIST), "as": "md", "title": "attention 由來"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("text/plain"))
        self.assertIn("# attention 由來", r.text)
        self.assertIn("**副手：**", r.text)
        self.assertIn("https://a/1", r.text)

    def test_chat_export_urls(self):                        # T010
        app = build_app(temp_db())
        r = TestClient(app).post("/chat/export", data={
            "history": json.dumps(_HIST), "as": "urls"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text.strip().splitlines(), ["https://a/1", "https://a/2"])

    def test_chat_export_empty_history_ok(self):            # T005 空不崩
        app = build_app(temp_db())
        r = TestClient(app).post("/chat/export", data={"history": "[]", "as": "urls"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text.strip(), "")


class TestConversationExport(unittest.TestCase):
    def _seed(self, db):
        repo = Repository(db)
        cid = repo.save_conversation("存下的對話", _HIST, None)
        repo.close()
        return cid

    def test_conversation_export_md(self):                  # T005
        db = temp_db()
        app = build_app(db)
        cid = self._seed(db)
        r = TestClient(app).get(f"/conversations/{cid}/export?as=md")
        self.assertEqual(r.status_code, 200)
        self.assertIn("# 存下的對話", r.text)

    def test_conversation_export_urls(self):                # T010
        db = temp_db()
        app = build_app(db)
        cid = self._seed(db)
        r = TestClient(app).get(f"/conversations/{cid}/export?as=urls")
        self.assertEqual(r.text.strip().splitlines(), ["https://a/1", "https://a/2"])

    def test_conversation_export_404(self):                 # T005
        app = build_app(temp_db())
        r = TestClient(app).get("/conversations/999/export?as=md")
        self.assertEqual(r.status_code, 404)


class TestRootExport(unittest.TestCase):
    def _seed_root(self, db):
        repo = Repository(db)
        wid = repo.add_why_node("attention＝內容加權", ["https://a/1", "https://a/2"],
                                [], False, 0, _now(),
                                ladder=["表面：怎麼加權", "bedrock：內容決定"])
        repo.anoint_why_node(wid)
        repo.close()
        return wid

    def test_root_export_md(self):                          # T015
        db = temp_db()
        app = build_app(db)
        wid = self._seed_root(db)
        r = TestClient(app).get(f"/roots/{wid}/export?as=md")
        self.assertEqual(r.status_code, 200)
        self.assertIn("# attention＝內容加權", r.text)
        self.assertIn("bedrock：內容決定", r.text)

    def test_root_export_urls(self):                        # T015
        db = temp_db()
        app = build_app(db)
        wid = self._seed_root(db)
        r = TestClient(app).get(f"/roots/{wid}/export?as=urls")
        self.assertEqual(r.text.strip().splitlines(), ["https://a/1", "https://a/2"])

    def test_root_export_404(self):                         # T015
        app = build_app(temp_db())
        r = TestClient(app).get("/roots/999/export?as=md")
        self.assertEqual(r.status_code, 404)


class TestReadOnlyGuard(unittest.TestCase):
    def test_export_does_not_mutate_or_pollute(self):       # T018 原則 6
        db = temp_db()
        app = build_app(db)
        repo = Repository(db)
        # 存一段含發想的對話
        secret = "SECRET_FANTASY_不該進場"
        repo.save_conversation("發想", [
            {"role": "user", "content": secret}], None)
        wid = repo.add_why_node("真根因", ["https://a/1"], [], False, 0, _now(),
                                ladder=["b"])
        repo.anoint_why_node(wid)
        repo.close()

        client = TestClient(app)
        client.get("/conversations/1/export?as=md")
        client.get(f"/roots/{wid}/export?as=md")
        client.post("/chat/export", data={"history": json.dumps([
            {"role": "user", "content": secret}]), "as": "md"})

        # 匯出後 DB 內容不變
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), 1)
        self.assertEqual(len(repo.list_why_nodes("anointed")), 1)
        repo.close()

        # 場脈絡（system prompt）只來自冊封根因、不含發想對話內容
        from learnnews.chat.field_chat import build_field_system_prompt
        repo = Repository(db)
        roots = repo.list_why_nodes("anointed")
        repo.close()
        sysp = build_field_system_prompt(roots)
        self.assertNotIn(secret, sysp)


if __name__ == "__main__":
    unittest.main()
