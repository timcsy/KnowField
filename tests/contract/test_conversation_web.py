"""spec 023：對話由來存檔 web——兩存檔點、查閱、不入地基守衛、友善。"""

import json
import unittest

from fastapi.testclient import TestClient

from learnnews.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_HIST = json.dumps([
    {"role": "user", "content": "attention 為何加權？"},
    {"role": "assistant", "content": "因為置換對稱逼出加總，內容決定→加權。"}])


class TestConversationWeb(unittest.TestCase):
    def test_anoint_with_save_convo_links_root(self):            # T007 冊封時連同存
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda messages: "attention 加權的由來"
        TestClient(app).post("/chat/anoint", data={
            "claim": "attention＝內容加權聚合", "ladder": "置換對稱→加總",
            "evidence_urls": "", "save_convo": "1", "history": _HIST},
            follow_redirects=True)
        repo = Repository(db)
        anointed = repo.list_why_nodes("anointed")
        self.assertEqual(len(anointed), 1)
        prov = repo.why_node_provenance()
        self.assertIn(anointed[0].id, prov)                      # 根因連到對話
        conv = repo.get_conversation(prov[anointed[0].id])
        self.assertEqual(conv.title, "attention 加權的由來")
        self.assertEqual(len(conv.messages), 2)                  # 整段存下
        repo.close()

    def test_anoint_without_save_convo_no_conversation(self):    # T007 未勾→只冊封
        db = temp_db()
        app = build_app(db)
        TestClient(app).post("/chat/anoint", data={
            "claim": "只冊封", "ladder": "", "evidence_urls": "", "history": _HIST},
            follow_redirects=True)
        repo = Repository(db)
        self.assertEqual(len(repo.list_why_nodes("anointed")), 1)
        self.assertEqual(len(repo.list_conversations()), 0)      # 沒存對話
        repo.close()

    def test_independent_save(self):                             # T008 獨立存
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda messages: "獨立探索"
        TestClient(app).post("/chat/save", data={"history": _HIST}, follow_redirects=True)
        repo = Repository(db)
        convs = repo.list_conversations()
        self.assertEqual(len(convs), 1)
        self.assertEqual(convs[0].title, "獨立探索")
        self.assertIsNone(convs[0].why_node_id)                  # 未連根因
        repo.close()

    def test_empty_save_friendly(self):                          # T008 空對話不存
        db = temp_db()
        app = build_app(db)
        TestClient(app).post("/chat/save", data={"history": "[]"}, follow_redirects=True)
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), 0)
        repo.close()

    def test_saved_conversation_not_in_chat_context(self):       # T011 不入地基（核心守衛）
        db = temp_db()
        # 存一段含「發想幻想」的對話
        repo = Repository(db)
        repo.save_conversation("危險發想", [
            {"role": "user", "content": "SECRET_FANTASY_絕不能進場脈絡"}], None)
        repo.close()
        app = build_app(db)
        captured = {}

        class _Spy:
            def reply(self, messages): captured["sys"] = messages[0]["content"]; return "ok"
        app.state.chat_backend_for_test = _Spy()
        app.state.chat_search_for_test = lambda m: []
        TestClient(app).post("/chat", data={"history": "[]", "message": "嗨"},
                             follow_redirects=True)
        self.assertNotIn("SECRET_FANTASY", captured.get("sys", ""))   # 存下的對話沒被注入場脈絡

    def test_conversations_list_and_view(self):                  # T012 查閱
        db = temp_db()
        repo = Repository(db)
        cid = repo.save_conversation("某段由來", [
            {"role": "user", "content": "問X"}, {"role": "assistant", "content": "答X"}], None)
        repo.close()
        c = TestClient(build_app(db))
        r = c.get("/conversations")
        self.assertIn("某段由來", r.text)                        # 清單
        r2 = c.get(f"/conversations/{cid}")
        self.assertEqual(r2.status_code, 200)
        self.assertIn("答X", r2.text)                            # 單篇含整段

    def test_roots_shows_provenance_link(self):                  # T012 根因由來連結
        db = temp_db()
        repo = Repository(db)
        wid = repo.add_why_node("根因", [], [], False, 0, "2026-07-29", ladder=["階"])
        repo.anoint_why_node(wid)
        cid = repo.save_conversation("由來", [{"role": "user", "content": "x"}], wid)
        repo.close()
        r = TestClient(build_app(db)).get("/roots")
        self.assertIn(f"/conversations/{cid}", r.text)           # 「← 由來」連結

    def test_title_failure_still_saves(self):                    # T014 標題失敗仍存
        db = temp_db()
        app = build_app(db)

        def boom(messages): raise RuntimeError("標題炸")
        app.state.title_factory = boom
        r = TestClient(app, raise_server_exceptions=False).post(
            "/chat/save", data={"history": _HIST}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Traceback", r.text)
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), 1)      # 仍存成功（退回標題）
        repo.close()


if __name__ == "__main__":
    unittest.main()
