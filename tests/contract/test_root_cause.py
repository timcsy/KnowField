"""T011/T015-T017 [US1-US4]：閉環（冊封根因→ask 檢索）＋web 萃取/冊封/退回/失敗。"""

import unittest

from fastapi.testclient import TestClient

from learnnews.rag.service import RagService
from learnnews.ranking.embeddings import HashingEmbedder
from learnnews.rag.answerer import StubAnswerer
from learnnews.rootcause.extract import Candidate
from learnnews.sources.base import SourceUnavailable
from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db
from tests.web_helpers import build_app, seed_digest as web_seed  # noqa: F401


class TestClosedLoop(unittest.TestCase):
    def test_anointed_why_node_retrieved_by_ask(self):
        # US3 閉環：冊封一個根因（claim 含關鍵詞）→ RagService 檢索得到、sources 含其證據
        db = temp_db()
        repo = Repository(db)
        wid = repo.add_why_node(
            claim="transformer attention 有效的根因是直接建模長程依賴",
            evidence_urls=["https://root/evidence"], touchstones=[], fog_flag=False,
            source_entry_id=1, created_at="2026-07-25")
        repo.anoint_why_node(wid)

        svc = RagService(repo, HashingEmbedder(), StubAnswerer(),
                         min_score=0.02, root_weight=2.0)
        ans = svc.answer("attention 長程依賴")
        self.assertFalse(ans.no_material)
        self.assertIn("https://root/evidence", [s.url for s in ans.sources])  # 檢索到根因
        repo.close()


def _seed_one(db):
    """種一則種子，回其 entry_id（供 /whynode/extract）。"""
    repo = Repository(db)
    from learnnews.models import Article, Item
    eid = repo.ingest_seed(
        Item(source_id="s", external_id="", title="種子文", url="https://seed/1"),
        Article(item_id=0, body="一段可萃取的內容。", source_url="https://seed/1",
                headline="種子文"), source_class="explainer")
    repo.close()
    return eid


class TestRootCauseWeb(unittest.TestCase):
    def _app_with_stub(self, db):
        app = build_app(db)
        app.state.extractor_factory = lambda: type("E", (), {
            "extract": staticmethod(lambda t, b: Candidate(
                claim="候選根因主張", touchstones=[{"name": "機制", "passed": True}],
                ladder=["表面 why 層", "bedrock：資訊理論極限"],
                fog_flag=False, no_material=False))})()
        return app

    def test_extract_creates_candidate_and_lists(self):
        db = temp_db()
        eid = _seed_one(db)
        app = self._app_with_stub(db)
        client = TestClient(app)
        r = client.post("/whynode/extract", data={"entry_id": eid}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("候選根因主張", r.text)
        self.assertIn("AI 推斷", r.text)                       # 明標推斷
        self.assertIn("機制", r.text)                          # 試金石逐條
        self.assertIn("bedrock", r.text)                       # why 階梯（挖到底）
        self.assertIn("資訊理論極限", r.text)                   # 階梯最底層顯示
        # /library 種子有「萃取根因」鈕
        lib = client.get("/library")
        self.assertIn("/whynode/extract", lib.text)

    def test_anoint_and_remove(self):
        db = temp_db()
        repo = Repository(db)
        wid = repo.add_why_node("候選 X", ["https://a/1"], [], False, 1, "2026-07-25")
        repo.close()
        app = self._app_with_stub(db)
        client = TestClient(app)
        client.post("/whynode/anoint", data={"id": wid, "claim": "冊封後 X"})
        repo = Repository(db)
        self.assertEqual(repo.list_why_nodes("anointed")[0].claim, "冊封後 X")
        repo.close()
        client.post("/whynode/remove", data={"id": wid})
        repo = Repository(db)
        self.assertEqual(repo.list_why_nodes(), [])
        repo.close()

    def test_extract_failure_friendly(self):
        db = temp_db()
        eid = _seed_one(db)
        app = build_app(db)

        def boom():
            return type("E", (), {"extract": staticmethod(
                lambda t, b: (_ for _ in ()).throw(SourceUnavailable("模擬未設金鑰")))})()
        app.state.extractor_factory = boom
        r = TestClient(app, raise_server_exceptions=False).post(
            "/whynode/extract", data={"entry_id": eid}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)                  # 非 500
        self.assertNotIn("Traceback", r.text)
        repo = Repository(db)
        self.assertEqual(repo.list_why_nodes(), [])           # 失敗不建候選
        repo.close()

    def test_extract_no_material(self):
        db = temp_db()
        eid = _seed_one(db)
        app = build_app(db)
        app.state.extractor_factory = lambda: type("E", (), {"extract": staticmethod(
            lambda t, b: Candidate(no_material=True))})()
        client = TestClient(app)
        client.post("/whynode/extract", data={"entry_id": eid}, follow_redirects=True)
        repo = Repository(db)
        self.assertEqual(repo.list_why_nodes(), [])           # no_material 不建候選
        repo.close()


if __name__ == "__main__":
    unittest.main()
