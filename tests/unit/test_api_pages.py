"""spec 033 里程碑二/三：其餘頁 /api 端點覆蓋（取代被退場的舊 Jinja web 測）。

離線注入，零外呼（教訓 1）。守衛：人閘門冊封、收進不自動進地基。
"""

import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from knowfield.ingest.service import ContentIngestService
from knowfield.rootcause.extract import Candidate
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class StubEmbedder:
    def embed(self, text):
        return [1.0, 0.0]

    def embed_many(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _seed_source(db, title="養貓", body=None):
    repo = Repository(db)
    ContentIngestService(repo, StubEmbedder()).ingest_text(
        body or ("# 貓\n" + ("貓要吃貓糧與用貓砂很重要。" * 40)), title=title)
    url = repo.list_source_groups()[0]["url"]
    repo.close()
    return url


class TestApiLibrarySource(unittest.TestCase):
    def test_library_lists_sources(self):
        db = temp_db()
        _seed_source(db)
        r = TestClient(build_app(db)).get("/api/library").json()
        self.assertEqual(len(r["sources"]), 1)
        self.assertEqual(r["sources"][0]["title"], "養貓")

    def test_source_detail_and_meta_and_reclassify_and_remove(self):
        db = temp_db()
        url = _seed_source(db)
        c = TestClient(build_app(db))
        d = c.get(f"/api/source?u={url}").json()
        self.assertTrue(d["found"])
        self.assertIn("貓", d["markdown"])
        c.post("/api/source/meta", json={"u": url, "note": "為了養貓", "ingested_at": "2026-08"})
        c.post("/api/library/reclassify", json={"url": url, "source_class": "explainer"})
        r = c.get("/api/library").json()["sources"][0]
        self.assertEqual(r["note"], "為了養貓")
        self.assertEqual(r["source_class"], "explainer")
        c.post("/api/library/remove", json={"url": url})
        self.assertEqual(len(c.get("/api/library").json()["sources"]), 0)

    def test_source_distill_human_gate(self):
        db = temp_db()
        url = _seed_source(db)
        app = build_app(db)
        app.state.extractor_for_test = SimpleNamespace(
            extract=lambda title, body: Candidate(
                claim="根因：貓要吃貓糧是因為肉食性", ladder=["表面", "bedrock"],
                touchstones=[], fog_flag=False, no_material=False))
        c = TestClient(app)
        r = c.post("/api/source/distill", json={"u": url}).json()
        self.assertTrue(r["ok"])
        repo = Repository(db)
        self.assertEqual(len(repo.list_why_nodes("candidate")), 1)   # 只候選
        self.assertEqual(repo.list_why_nodes("anointed"), [])        # 沒自動冊封（人閘門）
        repo.close()


class TestApiIngest(unittest.TestCase):
    def test_ingest_paste_and_url(self):
        db = temp_db()
        app = build_app(db)
        app.state.web_fetch = lambda u: (
            "<html><head><title>狗文</title></head><body><article><h1>養狗指南</h1><p>"
            + "狗很忠誠也要吃飯。" * 40 + "</p></article></body></html>")
        c = TestClient(app)
        r1 = c.post("/api/ingest/paste",
                    json={"text": "貓要吃貓糧與用貓砂。" * 30, "title": "貓筆記"}).json()
        self.assertEqual(r1["status"], "ingested")
        self.assertGreaterEqual(r1["count"], 1)
        r2 = c.post("/api/ingest/url", json={"url": "https://blog/x", "title": "狗文"}).json()
        self.assertEqual(r2["status"], "ingested")
        self.assertEqual(len(c.get("/api/library").json()["sources"]), 2)

    def test_ingest_paste_empty(self):
        r = TestClient(build_app(temp_db())).post("/api/ingest/paste", json={"text": "  "}).json()
        self.assertEqual(r["status"], "empty")


class TestApiConversations(unittest.TestCase):
    def _save(self, db, title="對話一"):
        repo = Repository(db)
        cid = repo.save_conversation(title, [{"role": "user", "content": "hi"},
                                             {"role": "assistant", "content": "yo"}])
        repo.close()
        return cid

    def test_list_detail_rename(self):
        db = temp_db()
        cid = self._save(db)
        c = TestClient(build_app(db))
        lst = c.get("/api/conversations").json()
        self.assertEqual(len(lst["permanent"]), 1)
        d = c.get(f"/api/conversations/{cid}").json()
        self.assertTrue(d["found"])
        self.assertEqual(len(d["messages"]), 2)
        c.post(f"/api/conversations/{cid}/rename", json={"title": "改了名"})
        self.assertEqual(c.get("/api/conversations").json()["permanent"][0]["title"], "改了名")

    def test_dedupe_preview_and_apply(self):
        db = temp_db()
        self._save(db, "重複")
        repo = Repository(db)      # 存一份相同指紋的（觸發重複）
        repo.conn.execute("INSERT INTO conversations (title, messages, created_at)"
                          " VALUES (%s,%s,%s)",
                          ("重複複本",
                           repo.conn.execute("SELECT messages FROM conversations LIMIT 1").fetchone()["messages"],
                           "2026-08-06T00:00:00Z"))
        repo.conn.commit()
        repo.close()
        c = TestClient(build_app(db))
        p = c.get("/api/conversations-dedupe/preview").json()
        self.assertGreaterEqual(p["n_extra"], 1)
        a = c.post("/api/conversations-dedupe/apply", json={}).json()
        self.assertTrue(a["ok"])


if __name__ == "__main__":
    unittest.main()
