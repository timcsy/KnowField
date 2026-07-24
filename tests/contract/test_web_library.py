"""T006/T012 [US1/US3]：/library 列種子/空狀態、刪除、每日流唯讀。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.models import Article, Item
from learnnews.store.repository import Repository
from tests.rag_helpers import make_entry, seed_digest, temp_db
from tests.web_helpers import build_app


def _add_seed(db, title, url, body, cls="ordinary"):
    repo = Repository(db)
    item = Item(source_id="seed", external_id="", title=title, url=url)
    eid = repo.ingest_seed(item, Article(item_id=0, body=body, source_url=url,
                                         headline=title), cls)
    repo.close()
    return eid


class TestWebLibrary(unittest.TestCase):
    def test_lists_seeds_not_daily(self):
        db = temp_db()
        repo = Repository(db)
        seed_digest(repo, "2026-07-23",
                    [make_entry(1, "DailyOnly", "https://a/daily", "DailyHead", "b")])
        repo.close()
        _add_seed(db, "SeedOnly", "https://a/seed", "body")
        r = TestClient(build_app(db)).get("/library")
        self.assertEqual(r.status_code, 200)
        self.assertIn("SeedOnly", r.text)
        self.assertNotIn("DailyOnly", r.text)      # 每日流不現身（FR-005）
        self.assertNotIn("DailyHead", r.text)

    def test_empty_state(self):
        r = TestClient(build_app(temp_db())).get("/library")
        self.assertIn("還沒有種子", r.text)

    def test_remove_deletes(self):
        db = temp_db()
        eid = _add_seed(db, "ToDelete", "https://a/x", "body")
        client = TestClient(build_app(db))
        client.post("/library/remove", data={"entry_id": str(eid)})
        self.assertNotIn("ToDelete", client.get("/library").text)

    def test_remove_daily_flow_is_noop(self):
        db = temp_db()
        repo = Repository(db)
        seed_digest(repo, "2026-07-23",
                    [make_entry(1, "DailyKeep", "https://a/daily", "H", "b")])
        daily_id = repo.list_corpus_entries(today=True)[0].entry_id
        repo.close()
        TestClient(build_app(db)).post("/library/remove",
                                       data={"entry_id": str(daily_id)})
        repo = Repository(db)                       # 每日流仍在
        self.assertEqual(len(repo.list_corpus_entries(today=True)), 1)
        repo.close()

    def test_reclassify_shows_explainer(self):
        db = temp_db()
        eid = _add_seed(db, "Seed", "https://a/1", "body", cls="ordinary")
        client = TestClient(build_app(db))
        client.post("/library/reclassify",
                    data={"entry_id": str(eid), "source_class": "explainer"})
        self.assertIn("解說文", client.get("/library").text)


if __name__ == "__main__":
    unittest.main()
