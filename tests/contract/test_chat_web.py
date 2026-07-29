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
        app.state.chat_factory = lambda history, message, brainstorm=False: (
            seen.update(history=history, message=message, brainstorm=brainstorm)
            or ("（回應）[1]", [{"n": 1, "url": "https://a/1", "title": "來源A"}]))
        hist = [{"role": "user", "content": "前"}, {"role": "assistant", "content": "答"}]
        r = TestClient(app).post("/chat", data={"history": json.dumps(hist),
                                                "message": "新問題"}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(seen["message"], "新問題")
        self.assertEqual(seen["history"], hist)                  # 多輪脈絡帶回
        self.assertIn("新問題", r.text)
        self.assertIn("（回應）", r.text)
        self.assertIn("https://a/1", r.text)                     # 每輪自動附來源
        self.assertIn("src-1", r.text)                           # 維基式錨點（本則 scoped）

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
        app.state.chat_search_for_test = lambda message: []   # 不打外部搜尋
        r = TestClient(app).post("/chat", data={"history": "[]", "message": "嗨"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("MATCH 我的根因", captured.get("sys", ""))

    def test_anoint_is_human_gated(self):                        # T010 人閘門
        db = temp_db()
        app = build_app(db)
        # 聊天/distill 不寫 bedrock
        app.state.chat_factory = lambda history, message, brainstorm=False: "（回應）"
        app.state.distill_factory = lambda history: [
            CandidateDraft(claim="蒸餾出的根因", kind="能推導/證明",
                           ladder=["因為A"], evidence_urls=["https://a/1"]),
            CandidateDraft(claim="第二層那條", kind="觀察到的規律", ladder=["觀察B"])]
        c = TestClient(app)
        c.post("/chat", data={"history": "[]", "message": "聊"}, follow_redirects=True)
        repo = Repository(db)
        self.assertEqual(len(repo.list_why_nodes("anointed")), 0)   # 對話不自動冊封
        repo.close()
        # distill 回多條候選（含類型）
        r = c.post("/chat/distill", data={"history": "[]"}, follow_redirects=True)
        self.assertIn("蒸餾出的根因", r.text)
        self.assertIn("第二層那條", r.text)                       # 多條都顯示
        self.assertIn("觀察到的規律", r.text)                     # 類型徽章
        # 人按冊封 → 進場
        c.post("/chat/anoint", data={"claim": "蒸餾出的根因", "ladder": "因為A\n所以B",
                                     "evidence_urls": "https://a/1"}, follow_redirects=True)
        repo = Repository(db)
        anointed = repo.list_why_nodes("anointed")
        self.assertEqual(len(anointed), 1)
        self.assertEqual(anointed[0].claim, "蒸餾出的根因")
        repo.close()

    def test_stream_sse(self):                                   # 串流：token 事件＋done＋來源
        app = build_app(temp_db())
        app.state.chat_search_for_test = lambda q: [
            SearchResult("相關", "https://good/1", "有料")]

        class _B:
            def reply(self, m): return "flow matching query"          # search_query 用
            def stream(self, m):
                yield "這句有依據 "
                yield "[1]。"
        app.state.chat_backend_for_test = _B()
        r = TestClient(app).post("/chat/stream", data={"history": "[]", "message": "問"})
        self.assertEqual(r.status_code, 200)
        self.assertIn('"type": "token"', r.text)                 # 有逐段 token
        self.assertIn('"type": "done"', r.text)
        self.assertIn("https://good/1", r.text)                  # 被引用來源在 done
        self.assertIn("找關鍵字", r.text)                        # 分段進度

    def test_stream_brainstorm_no_search(self):                  # 串流腦力激盪：不撒網
        app = build_app(temp_db())
        called = {"n": 0}
        app.state.chat_search_for_test = lambda q: called.update(n=called["n"] + 1) or []
        app.state.chat_backend_for_test = type("B", (), {
            "reply": lambda self, m: "q", "stream": lambda self, m: iter(["發想"])})()
        r = TestClient(app).post("/chat/stream",
                                 data={"history": "[]", "message": "亂想", "brainstorm": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(called["n"], 0)                         # 腦力激盪→不搜尋

    def test_failure_friendly(self):                             # T016
        app = build_app(temp_db())

        def boom(history, message, brainstorm=False):
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

    def test_brainstorm_skips_search(self):                      # 腦力激盪＝不撒網
        app = build_app(temp_db())
        seen = {}
        app.state.chat_factory = lambda history, message, brainstorm=False: (
            seen.update(bs=brainstorm) or ("（發想）", []))
        c = TestClient(app)
        c.post("/chat", data={"history": "[]", "message": "亂想", "brainstorm": "1"},
               follow_redirects=True)
        self.assertTrue(seen["bs"])                              # 旗標傳到 factory
        seen.clear()
        c.post("/chat", data={"history": "[]", "message": "正經問"}, follow_redirects=True)
        self.assertFalse(seen["bs"])                             # 未勾＝照常撒網

    def test_default_brainstorm_no_sources(self):                # 預設路徑：腦力激盪不附來源
        app = build_app(temp_db())
        called = {"search": 0}
        app.state.chat_search_for_test = lambda m: called.update(search=called["search"] + 1) or []
        app.state.chat_backend_for_test = type("B", (), {"reply": lambda self, m: "（發想）"})()
        r = TestClient(app).post("/chat", data={"history": "[]", "message": "亂想",
                                                "brainstorm": "1"}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(called["search"], 0)                   # 腦力激盪→根本沒呼叫搜尋

    def test_only_cited_sources_shown(self):                     # 只列被引用的來源，濾垃圾
        app = build_app(temp_db())
        app.state.chat_search_for_test = lambda q: [
            SearchResult("相關", "https://good/2", "有料"),        # 會被 [1]? 由回答決定
            SearchResult("垃圾", "https://junk/x", "無關")]
        # backend：search_query 回 query；答案只引用 [1]（即第 1 條來源）
        app.state.chat_backend_for_test = type("B", (), {
            "reply": lambda self, m: "這句有依據 [1]。第二條沒引用。"})()
        r = TestClient(app).post("/chat", data={"history": "[]", "message": "問"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("https://good/2", r.text)                  # 被引用的（第1條）有列
        self.assertNotIn("https://junk/x", r.text)              # 沒被引用的（第2條）不列


if __name__ == "__main__":
    unittest.main()
