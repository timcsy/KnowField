"""spec 022：/chat 路由——多輪、場脈絡、冊封人閘門、佐證、失敗/場空友善。"""

import json
import unittest

from fastapi.testclient import TestClient

from learnnews.chat.field_chat import CandidateDraft
from learnnews.models import Article, Item
from learnnews.search.websearch import SearchResult
from learnnews.sources.base import SourceUnavailable
from learnnews.store.repository import Repository
from tests.web_helpers import build_app, temp_db


def _anoint(db, claim):
    repo = Repository(db)
    wid = repo.add_why_node(claim, [], [], False, 0, "2026-07-29", ladder=["階梯"])
    repo.anoint_why_node(wid)
    repo.close()


class TestChatWeb(unittest.TestCase):
    def test_get_chat_page(self):                                # T008
        r = TestClient(build_app(temp_db())).get("/chat")
        self.assertEqual(r.status_code, 200)
        self.assertIn("跟", r.text)                              # 頁在

    def test_post_multiturn(self):                               # T008
        app = build_app(temp_db())
        seen = {}
        app.state.chat_factory = lambda history, message: (
            seen.update(history=history, message=message) or "（回應）")
        hist = [{"role": "user", "content": "前"}, {"role": "assistant", "content": "答"}]
        r = TestClient(app).post("/chat", data={"history": json.dumps(hist),
                                                "message": "新問題"}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(seen["message"], "新問題")
        self.assertEqual(seen["history"], hist)                  # 多輪脈絡帶回
        self.assertIn("新問題", r.text)
        self.assertIn("（回應）", r.text)

    def test_default_factory_injects_field(self):                # T009 場脈絡
        db = temp_db()
        _anoint(db, "MATCH 我的根因")
        app = build_app(db)
        captured = {}
        # 覆寫 chat backend（stub 之上加 spy），確認 system 含根因
        import learnnews.web.app as appmod  # noqa: F401

        class _Spy:
            def reply(self, messages):
                captured["sys"] = messages[0]["content"]
                return "ok"
        # 直接測 FieldChat 有注入：走預設 chat_factory 但替換 backend 工廠
        app.state.chat_backend_for_test = _Spy()
        r = TestClient(app).post("/chat", data={"history": "[]", "message": "嗨"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("MATCH 我的根因", captured.get("sys", ""))

    def test_anoint_is_human_gated(self):                        # T010 人閘門
        db = temp_db()
        app = build_app(db)
        # 聊天/distill 不寫 bedrock
        app.state.chat_factory = lambda history, message: "（回應）"
        app.state.distill_factory = lambda history: CandidateDraft(
            claim="蒸餾出的根因", ladder=["因為A"], evidence_urls=["https://a/1"])
        c = TestClient(app)
        c.post("/chat", data={"history": "[]", "message": "聊"}, follow_redirects=True)
        repo = Repository(db)
        self.assertEqual(len(repo.list_why_nodes("anointed")), 0)   # 對話不自動冊封
        repo.close()
        # distill 回候選
        r = c.post("/chat/distill", data={"history": "[]"}, follow_redirects=True)
        self.assertIn("蒸餾出的根因", r.text)
        # 人按冊封 → 進場
        c.post("/chat/anoint", data={"claim": "蒸餾出的根因", "ladder": "因為A\n所以B",
                                     "evidence_urls": "https://a/1"}, follow_redirects=True)
        repo = Repository(db)
        anointed = repo.list_why_nodes("anointed")
        self.assertEqual(len(anointed), 1)
        self.assertEqual(anointed[0].claim, "蒸餾出的根因")
        repo.close()

    def test_cite_on_demand(self):                               # T014
        app = build_app(temp_db())
        app.state.cite_factory = lambda claim: [
            SearchResult("佐證", "https://a/1", "有人說")]
        r = TestClient(app).post("/chat/cite", data={"claim": "X 是 Y"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("https://a/1", r.text)

    def test_failure_friendly(self):                             # T016
        app = build_app(temp_db())

        def boom(history, message):
            raise SourceUnavailable("對話炸了")
        app.state.chat_factory = boom
        r = TestClient(app, raise_server_exceptions=False).post(
            "/chat", data={"history": "[]", "message": "x"}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Traceback", r.text)

    def test_empty_field_hint(self):                             # T016 場空
        app = build_app(temp_db())        # 無冊封根因
        r = TestClient(app).post("/chat", data={"history": "[]", "message": "嗨"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)   # 不崩（走 stub，場空 prompt）


if __name__ == "__main__":
    unittest.main()
