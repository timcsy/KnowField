"""spec 032 web：/source/distill → 候選進 /roots；冊封後 /roots 顯示來源由來；萃取失敗 best-effort。

離線注入 extractor_for_test（教訓 1）。萃取失敗導回 /source、不 500（教訓 3）。
"""

import unittest

from fastapi.testclient import TestClient

from learnnews.ingest.service import ContentIngestService
from learnnews.rootcause.extract import Candidate
from learnnews.sources.base import SourceUnavailable
from learnnews.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class StubEmbedder:
    def embed(self, text):
        return [1.0, 0.0]

    def embed_many(self, texts):
        return [[1.0, 0.0] for _ in texts]


class StubExtractor:
    def __init__(self, cand=None):
        self._cand = cand

    def extract(self, title, body):
        return self._cand or Candidate(
            claim="根因：X 因為 Y", ladder=["表面", "bedrock"],
            touchstones=[{"name": "機制", "passed": True}], fog_flag=False,
            no_material=False)


class BoomExtractor:
    def extract(self, title, body):
        raise SourceUnavailable("萃取暫時失敗")


def _seed_source(db) -> str:
    repo = Repository(db)
    ContentIngestService(repo, StubEmbedder()).ingest_text(
        "# 主題\n" + ("這是一段夠長的收進內容供整理。" * 30), title="測試來源")
    url = repo.list_source_groups()[0]["url"]
    repo.close()
    return url


def _candidate_count(db) -> int:
    repo = Repository(db)
    n = len(repo.list_why_nodes("candidate"))
    repo.close()
    return n


class TestSourceDistillWeb(unittest.TestCase):
    def test_distill_creates_candidate_visible_in_roots(self):
        db = temp_db()
        app = build_app(db)
        url = _seed_source(db)
        app.state.extractor_for_test = StubExtractor()
        c = TestClient(app)
        r = c.post("/source/distill", data={"u": url}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("/roots", r.headers["location"])
        self.assertIn("根因：X 因為 Y", c.get("/roots").text)      # 候選現身 /roots

    def test_anoint_then_shows_source_provenance(self):
        db = temp_db()
        app = build_app(db)
        url = _seed_source(db)
        app.state.extractor_for_test = StubExtractor()
        c = TestClient(app)
        c.post("/source/distill", data={"u": url})
        repo = Repository(db)
        wid = repo.list_why_nodes("candidate")[0].id
        repo.close()
        c.post("/whynode/anoint", data={"id": wid})
        self.assertIn("由來（你收進的來源）", c.get("/roots").text)

    def test_extract_failure_best_effort_no_500(self):
        db = temp_db()
        app = build_app(db)
        url = _seed_source(db)
        app.state.extractor_for_test = BoomExtractor()
        c = TestClient(app)
        r = c.post("/source/distill", data={"u": url}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("/source", r.headers["location"])           # 導回來源、非 500
        self.assertEqual(_candidate_count(db), 0)                 # 沒存半殘候選

    def test_source_button_present(self):
        db = temp_db()
        app = build_app(db)
        url = _seed_source(db)
        html = TestClient(app).get(f"/source?u={url}").text
        self.assertIn("整理成核心理解", html)                      # 詳情頁有鈕


if __name__ == "__main__":
    unittest.main()
