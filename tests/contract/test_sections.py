"""T006/T007 [US1/US3]：首頁分兩區、空區不顯示、舊條目落預設區。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.models import Article, Digest, DigestEntry, Item, Source
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db
from tests.web_helpers import build_app


def _entry(title, url, sid):
    return DigestEntry(item=Item(source_id=sid, external_id="", title=title, url=url),
                       rank=1, relevance_score=0.9, matched_topic="",
                       article=Article(item_id=0, body="b", source_url=url, headline=title))


class TestSectionsWeb(unittest.TestCase):
    def _seed_sources(self, db):
        repo = Repository(db)
        repo.upsert_source(Source("arxiv-cs", "arXiv", "paper", "arxiv_api", "https://x"))
        repo.upsert_source(Source("techcrunch-ai", "TechCrunch", "news", "rss", "https://y"))
        repo.close()

    def test_two_sections_each_side(self):
        db = temp_db()
        self._seed_sources(db)
        repo = Repository(db)
        repo.save_digest(Digest(date="2026-07-26", entries=[
            _entry("論文標題", "https://a/paper", "arxiv-cs"),
            _entry("新聞標題", "https://a/news", "techcrunch-ai")]))
        repo.close()
        r = TestClient(build_app(db)).get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("今日新聞", r.text)
        self.assertIn("基礎知識精選", r.text)
        # 論文在基礎區之後、新聞在新聞區——兩標題都在
        self.assertIn("論文標題", r.text)
        self.assertIn("新聞標題", r.text)

    def test_empty_foundational_section_hidden(self):
        db = temp_db()
        self._seed_sources(db)
        repo = Repository(db)
        repo.save_digest(Digest(date="2026-07-26", entries=[
            _entry("只有新聞", "https://a/news", "techcrunch-ai")]))
        repo.close()
        r = TestClient(build_app(db)).get("/")
        self.assertIn("今日新聞", r.text)
        self.assertNotIn("基礎知識精選", r.text)               # 空基礎區不顯示

    def test_unknown_source_id_falls_to_news_not_crash(self):
        db = temp_db()
        repo = Repository(db)
        repo.save_digest(Digest(date="2026-07-26", entries=[
            _entry("舊條目", "https://a/x", "")]))               # 舊資料 source_id=''
        repo.close()
        r = TestClient(build_app(db)).get("/")
        self.assertEqual(r.status_code, 200)                   # 不崩
        self.assertIn("舊條目", r.text)
        self.assertIn("今日新聞", r.text)                       # 落新聞區
        self.assertNotIn("基礎知識精選", r.text)


if __name__ == "__main__":
    unittest.main()
