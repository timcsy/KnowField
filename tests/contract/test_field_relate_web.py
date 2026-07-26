"""T011/T012 [US1/US4]：/field/relate 顯示關係、牴觸、失敗友善、不改場。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.field.relate import FieldRelation
from learnnews.models import Article, Item
from learnnews.rag.types import CorpusEntry
from learnnews.sources.base import SourceUnavailable
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db
from tests.web_helpers import build_app


def _seed(db, title, url):
    repo = Repository(db)
    eid = repo.ingest_seed(Item(source_id="s", external_id="", title=title, url=url),
                           Article(item_id=0, body="種子內容", source_url=url, headline=title))
    repo.close()
    return eid


class TestFieldRelateWeb(unittest.TestCase):
    def test_library_has_relate_button(self):
        db = temp_db()
        _seed(db, "種子文", "https://a/1")
        r = TestClient(build_app(db)).get("/library")
        self.assertIn("/field/relate", r.text)                # 種子有「關聯到我的場」

    def test_relate_shows_contradiction(self):
        db = temp_db()
        eid = _seed(db, "種子文", "https://a/1")
        app = build_app(db)
        app.state.field_relate_factory = lambda title, body, exclude_url=None: FieldRelation(
            kind="contradict",
            attractor=CorpusEntry(entry_id=-1, title="根因：X", url="https://a/r", body="根因 X"),
            reason="材料的結論與此根因相反", score=0.7)
        r = TestClient(app).post("/field/relate", data={"entry_id": eid}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("牴觸", r.text)                          # 牴觸明確顯示
        self.assertIn("材料的結論與此根因相反", r.text)         # grounded 理由
        self.assertIn("https://a/r", r.text)                   # 連到根因

    def test_relate_failure_friendly(self):
        db = temp_db()
        eid = _seed(db, "種子文", "https://a/1")
        app = build_app(db)

        def boom(title, body, exclude_url=None):
            raise SourceUnavailable("判關係服務炸了")
        app.state.field_relate_factory = boom
        r = TestClient(app, raise_server_exceptions=False).post(
            "/field/relate", data={"entry_id": eid}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)                   # 非 500
        self.assertNotIn("Traceback", r.text)

    def test_relate_does_not_change_field(self):
        db = temp_db()
        eid = _seed(db, "種子文", "https://a/1")
        repo = Repository(db)
        wid = repo.add_why_node("根因", ["https://a/r"], [], False, 1, "2026-07-26")
        repo.anoint_why_node(wid)
        repo.close()
        app = build_app(db)
        app.state.field_relate_factory = lambda title, body, exclude_url=None: FieldRelation(
            kind="contradict", attractor=None, reason="相反", score=0.7)
        TestClient(app).post("/field/relate", data={"entry_id": eid}, follow_redirects=True)
        repo = Repository(db)
        self.assertEqual(len(repo.list_why_nodes("anointed")), 1)  # 牴觸不自動退根因
        self.assertEqual(len(repo.list_seeds()), 1)                # 種子不動
        repo.close()


if __name__ == "__main__":
    unittest.main()
