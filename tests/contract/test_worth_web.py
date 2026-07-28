"""spec 021：/worth 路由——反逢迎綜合、收內容口、subject 解析、失敗友善。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.search.websearch import SearchResult
from learnnews.search.worthit import WorthItVerdict
from learnnews.sources.base import SourceUnavailable
from tests.web_helpers import build_app, temp_db


def _verdict(subject="Claude Opus 5"):
    return WorthItVerdict(
        subject=subject,
        verdict_md=f"**官方說法**：…／**真實用戶心得**：難搞（https://a/1）／**值不值得你**：試一週",
        sources=[SearchResult("心得", "https://a/1", "有人說難搞")],
        no_material=False)


class TestWorthWeb(unittest.TestCase):
    def test_get_form(self):                                     # T007
        r = TestClient(build_app(temp_db())).get("/worth")
        self.assertEqual(r.status_code, 200)
        self.assertIn("值不值得", r.text)

    def test_post_name_renders_verdict(self):                    # T007
        app = build_app(temp_db())
        seen = {}
        app.state.worth_factory = lambda subject: seen.update(subject=subject) or _verdict(subject)
        r = TestClient(app).post("/worth", data={"subject": "Claude Opus 5"},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(seen["subject"], "Claude Opus 5")
        self.assertIn("真實用戶心得", r.text)
        self.assertIn("https://a/1", r.text)                     # 引用可回核

    def test_content_derives_subject(self):                      # T008 收內容口
        app = build_app(temp_db())
        seen = {}
        app.state.worth_factory = lambda subject: seen.update(subject=subject) or _verdict(subject)
        # 只給內文（牆內）→ 由首行解出 subject
        TestClient(app).post("/worth", data={"content": "Claude Opus 5 好像很猛\n有人試過嗎"},
                             follow_redirects=True)
        self.assertIn("Claude Opus 5", seen["subject"])

    def test_unfetchable_url_does_not_crash(self):               # T008 抓不到不崩
        app = build_app(temp_db())
        called = {}
        app.state.worth_factory = lambda subject: called.update(subject=subject) or _verdict(subject)
        # 伺服器抓 url 會失敗（假 fetch 拋例外）→ 退回用 url 續跑、不崩
        app.state.worth_fetch_title = lambda url: (_ for _ in ()).throw(SourceUnavailable("403"))
        r = TestClient(app, raise_server_exceptions=False).post(
            "/worth", data={"url": "https://blocked.example/x"}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Traceback", r.text)
        self.assertTrue(called)                                  # 仍有跑（用 url 當 subject）

    def test_empty_prompts_friendly(self):                       # T008 三者皆空
        app = build_app(temp_db())
        calls = []
        app.state.worth_factory = lambda subject: calls.append(1) or _verdict(subject)
        r = TestClient(app).post("/worth", data={}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(calls, [])                              # 沒 subject 不呼叫
        self.assertIn("請貼", r.text)

    def test_failure_friendly(self):                             # T011
        app = build_app(temp_db())

        def boom(subject):
            raise SourceUnavailable("搜尋炸了")
        app.state.worth_factory = boom
        r = TestClient(app, raise_server_exceptions=False).post(
            "/worth", data={"subject": "x"}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Traceback", r.text)

    def test_no_material_friendly(self):                         # T012
        app = build_app(temp_db())
        app.state.worth_factory = lambda subject: WorthItVerdict(subject=subject, no_material=True)
        r = TestClient(app).post("/worth", data={"subject": "冷門到爆"}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("太新", r.text)


if __name__ == "__main__":
    unittest.main()
