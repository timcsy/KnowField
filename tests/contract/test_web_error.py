"""T007：後端失敗 → 友善繁中頁、無 traceback、非未處理 500。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.backends.openai_api import OpenAIError
from tests.web_helpers import build_app, temp_db


class TestWebError(unittest.TestCase):
    def test_backend_failure_friendly_page(self):
        app = build_app(temp_db())

        def boom(topic):
            raise OpenAIError("模擬 403 allocation_quarantined")

        app.state.pull_runner = boom
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/pull", params={"topic": "agent"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("暫時不可用", r.text)         # 友善繁中
        self.assertIn("offline", r.text)             # 提示離線退路
        self.assertNotIn("Traceback", r.text)        # 不噴堆疊


if __name__ == "__main__":
    unittest.main()
