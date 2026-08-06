"""階段 29 第1階段：對話章節持久化——切一次存起來，避免每次檢視重切（LLM 慢）。離線注入。"""

import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_MSGS = [{"role": "user", "content": "問一"}, {"role": "assistant", "content": "答一"},
         {"role": "user", "content": "問二"}, {"role": "assistant", "content": "答二"}]


def _seed(db):
    repo = Repository(db)
    cid = repo.save_conversation("長對話", _MSGS, None)
    repo.close()
    return cid


class TestChapterPersist(unittest.TestCase):
    def test_default_chapters_empty(self):
        db = temp_db()
        cid = _seed(db)
        self.assertEqual(Repository(db).get_conversation(cid).chapters, [])

    def test_segment_persists_and_reuses(self):           # 切一次→存→第二次讀不重切
        db = temp_db()
        cid = _seed(db)
        app = build_app(db)
        calls = []
        app.state.segment_factory = lambda m: calls.append(1) or [
            {"title": "第一章", "start": 1, "end": 2}, {"title": "第二章", "start": 3, "end": 4}]
        c = TestClient(app)
        r1 = c.get(f"/api/conversations/{cid}/segment").json()
        r2 = c.get(f"/api/conversations/{cid}/segment").json()
        self.assertEqual(len(calls), 1)                    # 只切一次（第二次讀持久化）
        self.assertEqual(r1["chapters"], r2["chapters"])
        self.assertEqual(len(r1["chapters"]), 2)
        self.assertEqual(len(Repository(db).get_conversation(cid).chapters), 2)   # 落庫

    def test_refresh_reslices(self):                       # refresh=1 強制重切
        db = temp_db()
        cid = _seed(db)
        app = build_app(db)
        calls = []
        app.state.segment_factory = lambda m: calls.append(1) or [{"title": "x", "start": 1, "end": 4}]
        c = TestClient(app)
        c.get(f"/api/conversations/{cid}/segment")
        c.get(f"/api/conversations/{cid}/segment?refresh=1")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
