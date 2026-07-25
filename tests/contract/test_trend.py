"""T007/T008 [US2/US3]：首頁熱詞 chips＋連 /pull?topic=；無材料優雅省略。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.models import Article, Digest, DigestEntry, Item
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db
from tests.web_helpers import build_app


def _entry(title):
    return DigestEntry(item=Item(source_id="s", external_id="", title=title, url="https://a/x"),
                       rank=1, relevance_score=0.9, matched_topic="",
                       article=Article(item_id=0, body="b", source_url="https://a/x", headline=title))


class TestTrendWeb(unittest.TestCase):
    def test_home_shows_trend_chips(self):
        db = temp_db()
        repo = Repository(db)
        for d in ("2026-07-23", "2026-07-24", "2026-07-25"):
            repo.save_digest(Digest(date=d, entries=[
                _entry("latent reasoning survey"), _entry("latent reasoning benchmark")]))
        repo.close()
        r = TestClient(build_app(db)).get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("latent", r.text)                       # 熱詞出現
        self.assertIn("/pull?topic=", r.text)                 # chip 連深挖

    def test_home_no_digest_omits_chips(self):
        r = TestClient(build_app(temp_db())).get("/")
        self.assertEqual(r.status_code, 200)                  # 非 500
        self.assertNotIn("今日高頻", r.text)                   # 無材料 → 不顯示熱詞區塊


if __name__ == "__main__":
    unittest.main()
