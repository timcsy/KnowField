"""T007：後端失敗——串流推 error 事件、無 traceback（不噴未處理 500）。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.backends.openai_api import OpenAIError
from tests.web_helpers import build_app, temp_db


class TestWebError(unittest.TestCase):
    def test_backend_failure_streams_error_event(self):
        app = build_app(temp_db())

        def boom(topic):
            raise OpenAIError("模擬 403 allocation_quarantined")

        app.state.pull_stream_factory = boom
        r = TestClient(app, raise_server_exceptions=False).get(
            "/pull/stream", params={"topic": "agent"})
        self.assertEqual(r.status_code, 200)          # SSE 已開始，回 error 事件
        self.assertIn("error", r.text)                # 推了 error 事件
        self.assertNotIn("Traceback", r.text)         # 不噴堆疊


if __name__ == "__main__":
    unittest.main()
