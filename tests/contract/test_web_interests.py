"""T017：/interests list／add／remove 反映變更。"""

import unittest

from fastapi.testclient import TestClient

from tests.web_helpers import build_app, temp_db


class TestWebInterests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(build_app(temp_db()))

    def test_add_then_list(self):
        self.client.post("/interests/add", data={"topic": "LLM 推理"},
                         follow_redirects=True)
        r = self.client.get("/interests")
        self.assertIn("LLM 推理", r.text)

    def test_remove(self):
        self.client.post("/interests/add", data={"topic": "編譯器"},
                         follow_redirects=True)
        self.client.post("/interests/remove", data={"topic": "編譯器"},
                         follow_redirects=True)
        r = self.client.get("/interests")
        self.assertNotIn("編譯器", r.text)


if __name__ == "__main__":
    unittest.main()
