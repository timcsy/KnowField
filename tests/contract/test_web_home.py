"""T009：GET / 首頁匯整——原文連結、圖內嵌、AI 圖標示、空狀態。"""

import unittest

from fastapi.testclient import TestClient

from tests.web_helpers import build_app, seed_digest, temp_db


class TestWebHome(unittest.TestCase):
    def test_home_shows_digest_with_links_and_images(self):
        db = temp_db()
        seed_digest(db)
        client = TestClient(build_app(db))
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        html = r.text
        self.assertIn("整理過的新聞標題", html)      # 整理標題
        self.assertIn("原標題：Original Title", html)  # 原標題溯源
        self.assertIn("https://a/1", html)             # 一鍵原文
        self.assertIn("https://img/x.jpg", html)       # 原文圖內嵌
        self.assertIn("第一段內容。", html)            # 散文
        self.assertIn("AI 示意・非原文", html)         # AI 圖標示

    def test_home_empty_state(self):
        client = TestClient(build_app(temp_db()))
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("還沒有匯整", r.text)


if __name__ == "__main__":
    unittest.main()
