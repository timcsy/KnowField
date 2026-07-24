"""web /ingest：種子收進框——表單、成功渲染、已在庫、失敗頁內攔（不噴 500）。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.seed.service import IngestResult
from learnnews.sources.base import SourceUnavailable
from tests.web_helpers import build_app, temp_db


class TestWebIngest(unittest.TestCase):
    def test_get_shows_form(self):
        r = TestClient(build_app(temp_db())).get("/ingest")
        self.assertEqual(r.status_code, 200)
        self.assertIn("收進知識庫", r.text)
        self.assertIn('action="/ingest"', r.text)

    def test_post_success_renders_title_and_link(self):
        app = build_app(temp_db())
        app.state.seed_ingest_factory = lambda ref, explainer: IngestResult(
            status="ingested", title="Attention Is All You Need",
            url="https://arxiv.org/abs/1706.03762",
            source_class="explainer" if explainer else "ordinary")
        r = TestClient(app).post("/ingest", data={"ref": "1706.03762", "explainer": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("已收進知識庫", r.text)
        self.assertIn("Attention Is All You Need", r.text)
        self.assertIn("arxiv.org/abs/1706.03762", r.text)   # 溯源
        self.assertIn("解說文", r.text)

    def test_post_exists(self):
        app = build_app(temp_db())
        app.state.seed_ingest_factory = lambda ref, explainer: IngestResult(
            status="exists", title="已存在的種子", url="https://a/1")
        r = TestClient(app).post("/ingest", data={"ref": "x"})
        self.assertIn("已在庫", r.text)

    def test_post_failure_inline_not_500(self):
        app = build_app(temp_db())

        def boom(ref, explainer):
            raise SourceUnavailable("模擬 404")

        app.state.seed_ingest_factory = boom
        r = TestClient(app, raise_server_exceptions=False).post(
            "/ingest", data={"ref": "https://bad/x"})
        self.assertEqual(r.status_code, 200)      # 頁內攔，非 500
        self.assertIn("收取失敗", r.text)
        self.assertNotIn("Traceback", r.text)


if __name__ == "__main__":
    unittest.main()
