"""T013：GET /pull——回主題結果、同主題二次不打後端（快取）、冷門空狀態。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.models import Article, Item
from learnnews.pull.types import PullEntry, PullResult
from tests.web_helpers import build_app, temp_db


def _fake_result(topic, empty=False):
    if empty:
        return PullResult(topic=topic, entries=[])
    art = Article(item_id=0, body="拉取散文。", source_url="https://a/1",
                  headline="拉取標題")
    item = Item(source_id="s", external_id="1", title="原標題", url="https://a/1")
    return PullResult(topic=topic, entries=[
        PullEntry(item=item, rank=1, relevance_score=0.9, article=art)])


class TestWebPull(unittest.TestCase):
    def test_pull_shows_result(self):
        app = build_app(temp_db())
        app.state.pull_runner = lambda t: _fake_result(t)
        client = TestClient(app)
        r = client.get("/pull", params={"topic": "agent"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("拉取標題", r.text)
        self.assertIn("https://a/1", r.text)

    def test_cache_avoids_second_backend_call(self):
        app = build_app(temp_db())
        calls = {"n": 0}

        def runner(topic):
            calls["n"] += 1
            return _fake_result(topic)

        app.state.pull_runner = runner
        client = TestClient(app)
        client.get("/pull", params={"topic": "agent"})
        client.get("/pull", params={"topic": "agent"})   # 同主題
        self.assertEqual(calls["n"], 1)                  # 只打一次後端（快取命中）

    def test_cold_topic_empty(self):
        app = build_app(temp_db())
        app.state.pull_runner = lambda t: _fake_result(t, empty=True)
        client = TestClient(app)
        r = client.get("/pull", params={"topic": "某冷門主題"})
        self.assertIn("查無", r.text)


if __name__ == "__main__":
    unittest.main()
