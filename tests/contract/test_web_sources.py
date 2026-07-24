"""T005/T010/T012 [US1/2/3]：/sources 列出/加/管理/不加壞來源/去重。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.cli.fetchers import build_adapters
from learnnews.models import Source
from learnnews.sources.base import SourceUnavailable
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db
from tests.web_helpers import build_app


def _src(sid="sub-blog", name="My Blog"):
    return Source(id=sid, name=name, type="blog", access_method="rss",
                  endpoint="https://blog/feed.xml", enabled=True)


def _ids(db, enabled_only=False):
    repo = Repository(db)
    ids = {s.id for s in repo.list_sources(enabled_only=enabled_only)}
    repo.close()
    return ids


class TestWebSources(unittest.TestCase):
    def test_get_lists(self):
        r = TestClient(build_app(temp_db())).get("/sources")
        self.assertEqual(r.status_code, 200)
        self.assertIn("追蹤", r.text)

    def test_add_source(self):
        app = build_app(temp_db())
        app.state.subscribe_factory = lambda url: _src()
        client = TestClient(app)
        r = client.post("/sources/add", data={"url": "https://blog/"})
        self.assertIn("已加入來源", r.text)
        self.assertIn("My Blog", client.get("/sources").text)

    def test_added_source_is_fetchable(self):
        db = temp_db()
        app = build_app(db)
        app.state.subscribe_factory = lambda url: _src()
        TestClient(app).post("/sources/add", data={"url": "https://blog/"})
        repo = Repository(db)
        srcs = repo.list_sources(enabled_only=True)
        repo.close()
        self.assertIn("sub-blog", {s.id for s in srcs})
        adapters = build_adapters(srcs)                     # 抓取管線自動帶入
        self.assertTrue(any(a.source_id == "sub-blog" for a in adapters))

    def test_bad_url_no_source_added(self):
        db = temp_db()
        app = build_app(db)

        def boom(url):
            raise SourceUnavailable("找不到 RSS")

        app.state.subscribe_factory = boom
        client = TestClient(app, raise_server_exceptions=False)
        client.get("/sources")                              # 先觸發預設來源種入
        before = _ids(db)
        r = client.post("/sources/add", data={"url": "https://x/"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("找不到 RSS", r.text)
        self.assertNotIn("Traceback", r.text)
        self.assertEqual(_ids(db), before)                  # 不加壞來源

    def test_dedup(self):
        app = build_app(temp_db())
        app.state.subscribe_factory = lambda url: _src()
        client = TestClient(app)
        client.post("/sources/add", data={"url": "https://blog/"})
        r = client.post("/sources/add", data={"url": "https://blog/"})
        self.assertIn("已在追蹤", r.text)

    def test_toggle_and_remove(self):
        db = temp_db()
        app = build_app(db)
        app.state.subscribe_factory = lambda url: _src()
        client = TestClient(app)
        client.post("/sources/add", data={"url": "https://blog/"})
        client.post("/sources/toggle", data={"source_id": "sub-blog", "enabled": "0"})
        self.assertNotIn("sub-blog", _ids(db, enabled_only=True))   # 停用不抓
        client.post("/sources/remove", data={"source_id": "sub-blog"})
        self.assertNotIn("sub-blog", _ids(db))                      # 刪除消失


if __name__ == "__main__":
    unittest.main()
