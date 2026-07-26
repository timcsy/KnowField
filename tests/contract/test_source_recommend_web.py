"""spec 020：場驅動來源推薦 web 路由——opt-in、場驅動清單、訂閱複用 add、失敗友善。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.sources.base import SourceUnavailable
from learnnews.sources.recommend import CandidateSource
from tests.web_helpers import build_app, temp_db


def _cands():
    return [
        CandidateSource(domain="foo.com", homepage="https://foo.com/",
                        feed_url="https://foo.com/feed", name="Foo Blog",
                        reason="★ 你冊封的種子/根因與它相近（場驅動）；有活躍 feed",
                        field_score=0.9, list_hits=2, has_feed=True,
                        already_subscribed=False),
        CandidateSource(domain="nofeed.com", homepage="https://nofeed.com/",
                        feed_url=None, name="nofeed.com",
                        reason="無 RSS——靠 web 活水/收進補", field_score=0.0,
                        list_hits=1, has_feed=False, already_subscribed=False),
    ]


class TestRecommendWeb(unittest.TestCase):
    def test_recommend_lists_candidates(self):                   # T006
        app = build_app(temp_db())
        app.state.recommend_factory = lambda: _cands()
        r = TestClient(app).post("/sources/recommend", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("foo.com", r.text)                         # 候選網域
        self.assertIn("場驅動", r.text)                          # 推薦理由
        self.assertIn("/sources/add", r.text)                    # 有 feed → 訂閱複用 add
        self.assertIn("https://foo.com/feed", r.text)            # 訂閱帶 feed_url
        self.assertIn("無 RSS", r.text)                          # 無 feed 標示

    def test_home_and_refresh_do_not_auto_recommend(self):       # T007（opt-in 守衛）
        app = build_app(temp_db())
        calls = []
        app.state.recommend_factory = lambda: calls.append(1) or []
        c = TestClient(app)
        c.get("/sources")
        c.get("/")
        self.assertEqual(calls, [])                               # 載入不自動撒網

    def test_recommend_failure_friendly(self):                   # T010
        app = build_app(temp_db())

        def boom():
            raise SourceUnavailable("搜尋服務炸了")
        app.state.recommend_factory = boom
        r = TestClient(app, raise_server_exceptions=False).post(
            "/sources/recommend", follow_redirects=True)
        self.assertEqual(r.status_code, 200)                     # 非 500
        self.assertNotIn("Traceback", r.text)

    def test_recommend_empty_friendly(self):                     # T011
        app = build_app(temp_db())
        app.state.recommend_factory = lambda: []
        r = TestClient(app).post("/sources/recommend", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("沒找到", r.text)                          # 友善空提示


if __name__ == "__main__":
    unittest.main()
