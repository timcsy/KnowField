"""spec 019：forward-pass 接每日流——匯整條目也能「關聯到我的場」。

複用 spec 018 引擎，只加觸發點（每日流條目）。涵蓋：
- get_entry_material 取種子/流/不存在（T001）
- get_last_digest 帶 entry_id（T002）
- /field/relate 吃流的條目 + 排除自己（T005/T006）
- _entry.html 有 id 顯鈕、無 id 無鈕（T008）
- 首頁載入不自動關聯（T010）
- 流的條目失敗友善 / 場空（T011/T012）
"""

import unittest

from fastapi.testclient import TestClient

from learnnews.field.relate import FieldRelation
from learnnews.models import Article, Digest, DigestEntry, Item
from learnnews.rag.types import CorpusEntry
from learnnews.sources.base import SourceUnavailable
from learnnews.store.repository import Repository
from learnnews.web.app import render_entry
from tests.web_helpers import build_app, temp_db


def _save_flow(db, headline="整理過的新聞標題", body="第一段。\n\n第二段。",
               url="https://flow/1", title="原始新聞標題"):
    """存一則每日流匯整，回其 digest_entries.id。"""
    repo = Repository(db)
    repo.save_digest(Digest(date="2026-07-26", entries=[
        DigestEntry(item=Item(source_id="s", external_id="1", title=title, url=url),
                    rank=1, relevance_score=0.9, matched_topic="agent",
                    article=Article(item_id=0, body=body, source_url=url,
                                    headline=headline))]))
    # 用既有 list_corpus_entries 取回 id（不依賴本增量的 get_last_digest 改動）
    eid = repo.list_corpus_entries()[0].entry_id
    repo.close()
    return eid


def _seed(db, title="種子文", url="https://seed/1", body="種子內容"):
    repo = Repository(db)
    eid = repo.ingest_seed(Item(source_id="s", external_id="", title=title, url=url),
                           Article(item_id=0, body=body, source_url=url, headline=title))
    repo.close()
    return eid


# --- Phase 2：repository 取材料 ---
class TestGetEntryMaterial(unittest.TestCase):
    def test_flow_entry(self):                                   # T001
        db = temp_db()
        eid = _save_flow(db, headline="整理標題", body="散文本體。", url="https://flow/1")
        repo = Repository(db)
        mat = repo.get_entry_material(eid)
        repo.close()
        self.assertEqual(mat, ("整理標題", "散文本體。", "https://flow/1"))  # headline 優先

    def test_seed_entry(self):                                   # T001
        db = temp_db()
        eid = _seed(db, title="種子文", url="https://seed/1", body="種子內容")
        repo = Repository(db)
        mat = repo.get_entry_material(eid)
        repo.close()
        self.assertEqual(mat, ("種子文", "種子內容", "https://seed/1"))

    def test_missing_returns_none(self):                         # T001
        db = temp_db()
        repo = Repository(db)
        self.assertIsNone(repo.get_entry_material(99999))
        repo.close()


class TestLastDigestCarriesId(unittest.TestCase):
    def test_entry_id_populated(self):                           # T002
        db = temp_db()
        eid = _save_flow(db)
        repo = Repository(db)
        d = repo.get_last_digest()
        repo.close()
        self.assertEqual(d.entries[0].entry_id, eid)


# --- Phase 3：US1 路由泛化吃流的條目 + 排除自己 ---
class TestRelateFlowWeb(unittest.TestCase):
    def test_relate_eats_flow_entry(self):                       # T005
        db = temp_db()
        eid = _save_flow(db, headline="整理標題", body="流的本體。", url="https://flow/1")
        app = build_app(db)
        seen = {}

        def spy(title, body, exclude_url=None):
            seen.update(title=title, body=body, exclude_url=exclude_url)
            return FieldRelation(kind="extend", attractor=None, reason="延伸", score=0.5)
        app.state.field_relate_factory = spy
        r = TestClient(app).post("/field/relate", data={"entry_id": eid},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(seen["title"], "整理標題")               # 用該條目材料
        self.assertEqual(seen["body"], "流的本體。")

    def test_relate_excludes_self(self):                         # T006
        db = temp_db()
        eid = _save_flow(db, url="https://flow/self")
        app = build_app(db)
        seen = {}
        app.state.field_relate_factory = lambda title, body, exclude_url=None: (
            seen.update(exclude_url=exclude_url)
            or FieldRelation(kind="extend", attractor=None, reason="x", score=0.5))
        TestClient(app).post("/field/relate", data={"entry_id": eid},
                             follow_redirects=True)
        self.assertEqual(seen["exclude_url"], "https://flow/self")  # 排除自己

    def test_missing_id_redirects_home(self):                    # T007 邊界
        db = temp_db()
        app = build_app(db)
        r = TestClient(app).post("/field/relate", data={"entry_id": 99999},
                                 follow_redirects=False)
        self.assertEqual(r.status_code, 303)


class TestEntryButton(unittest.TestCase):
    def _entry(self, entry_id):
        return DigestEntry(
            item=Item(source_id="s", external_id="1", title="標題", url="https://a/1"),
            rank=1, relevance_score=0.9, matched_topic="x",
            article=Article(item_id=0, body="內文。", source_url="https://a/1",
                            headline="標題"),
            entry_id=entry_id)

    def test_button_when_id(self):                               # T008
        html = render_entry(self._entry(7))
        self.assertIn("/field/relate", html)
        self.assertIn("關聯到我的場", html)
        self.assertIn("7", html)

    def test_no_button_when_no_id(self):                         # T008（pull 即時條目）
        html = render_entry(self._entry(None))
        self.assertNotIn("/field/relate", html)


# --- Phase 4：US2 按需，不自動 ---
class TestOnDemand(unittest.TestCase):
    def test_home_does_not_auto_relate(self):                    # T010
        db = temp_db()
        _save_flow(db)
        app = build_app(db)
        calls = []
        app.state.field_relate_factory = lambda *a, **k: calls.append(1)
        r = TestClient(app).get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("/field/relate", r.text)                   # 有按鈕
        self.assertEqual(calls, [])                              # 但載入不呼叫


# --- Phase 5：US3 失敗 / 場空 ---
class TestFlowFailureAndEmpty(unittest.TestCase):
    def test_flow_failure_friendly(self):                        # T011
        db = temp_db()
        eid = _save_flow(db)
        app = build_app(db)

        def boom(title, body, exclude_url=None):
            raise SourceUnavailable("判關係服務炸了")
        app.state.field_relate_factory = boom
        r = TestClient(app, raise_server_exceptions=False).post(
            "/field/relate", data={"entry_id": eid}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Traceback", r.text)

    def test_flow_empty_field(self):                             # T012（走既有離線引擎）
        db = temp_db()
        eid = _save_flow(db)                                     # 無任何吸引子（場空）
        app = build_app(db)                                      # 預設離線 field_relate
        r = TestClient(app).post("/field/relate", data={"entry_id": eid},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
