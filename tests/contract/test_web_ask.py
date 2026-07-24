"""web /ask：問答框——渲染答案＋來源、查無說無、離線整合、後端失敗攔友善頁。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.backends.openai_api import OpenAIError
from learnnews.rag.types import RagAnswer, Source
from learnnews.store.repository import Repository
from tests.rag_helpers import make_entry, seed_digest
from tests.web_helpers import build_app, temp_db


class TestWebAsk(unittest.TestCase):
    def test_ask_page_empty_shows_form(self):
        r = TestClient(build_app(temp_db())).get("/ask")
        self.assertEqual(r.status_code, 200)
        self.assertIn("問答", r.text)
        self.assertIn("/ask", r.text)          # 有問答表單

    def test_ask_renders_answer_and_sources(self):
        app = build_app(temp_db())
        app.state.rag_answer_factory = lambda q, today, lang: RagAnswer(
            text="這是可溯源的答案[1]",
            sources=[Source(n=1, title="來源標題", url="https://a/1")])
        r = TestClient(app).get("/ask", params={"q": "問題"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("這是可溯源的答案", r.text)
        self.assertIn("https://a/1", r.text)    # 一鍵原文（溯源）

    def test_ask_no_material(self):
        app = build_app(temp_db())
        app.state.rag_answer_factory = lambda q, today, lang: RagAnswer(no_material=True)
        r = TestClient(app).get("/ask", params={"q": "冷門主題"})
        self.assertIn("沒有相關材料", r.text)

    def test_ask_integration_offline(self):
        db = temp_db()
        repo = Repository(db)
        seed_digest(repo, "2026-07-23", [
            make_entry(1, "Agent paper", "https://a/agent", "Agent memory",
                       "agent memory retrieval systems")])
        repo.close()
        r = TestClient(build_app(db)).get("/ask", params={"q": "agent memory"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("https://a/agent", r.text)   # 走真正 RagService（離線）檢索到並溯源

    def test_ask_backend_failure_friendly(self):
        app = build_app(temp_db())

        def boom(q, today, lang):
            raise OpenAIError("模擬 403 allocation_quarantined")

        app.state.rag_answer_factory = boom
        r = TestClient(app, raise_server_exceptions=False).get(
            "/ask", params={"q": "問題"})
        self.assertEqual(r.status_code, 503)       # 友善錯誤頁，非 500
        self.assertNotIn("Traceback", r.text)


if __name__ == "__main__":
    unittest.main()
