"""T013：/pull 串流殼＋/pull/stream SSE——逐則卡片、快取、冷門空狀態。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.models import Article, Item
from learnnews.pull.types import PullEntry
from tests.web_helpers import build_app, temp_db


def _card_event(topic):
    art = Article(item_id=0, body="拉取散文。", source_url="https://a/1",
                  headline="拉取標題")
    item = Item(source_id="s", external_id="1", title="原標題", url="https://a/1")
    return {"type": "card", "progress": "1/1",
            "entry": PullEntry(item=item, rank=1, relevance_score=0.9, article=art)}


class TestWebPull(unittest.TestCase):
    def test_pull_page_is_streaming_shell(self):
        client = TestClient(build_app(temp_db()))
        r = client.get("/pull", params={"topic": "agent"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("/pull/stream", r.text)     # 殼會連 SSE 端點
        self.assertIn("progress", r.text)          # 有進度區

    def test_stream_emits_stage_and_card(self):
        app = build_app(temp_db())

        def fake(topic):
            yield {"type": "stage", "text": "抓到 3 則候選"}
            yield _card_event(topic)

        app.state.pull_stream_factory = fake
        r = TestClient(app).get("/pull/stream", params={"topic": "agent"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("抓到 3 則候選", r.text)     # 階段進度
        self.assertIn("拉取標題", r.text)           # 逐則卡片
        self.assertIn("https://a/1", r.text)        # 一鍵原文

    def test_stream_cache_avoids_second_backend_call(self):
        app = build_app(temp_db())
        calls = {"n": 0}

        def fake(topic):
            calls["n"] += 1
            yield _card_event(topic)

        app.state.pull_stream_factory = fake
        client = TestClient(app)
        client.get("/pull/stream", params={"topic": "agent"})
        client.get("/pull/stream", params={"topic": "agent"})   # 同主題
        self.assertEqual(calls["n"], 1)                          # 只算一次

    def test_stream_cold_topic_empty(self):
        app = build_app(temp_db())
        app.state.pull_stream_factory = lambda t: iter([{"type": "empty"}])
        r = TestClient(app).get("/pull/stream", params={"topic": "冷門"})
        self.assertIn("empty", r.text)


if __name__ == "__main__":
    unittest.main()
