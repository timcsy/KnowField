"""spec 027：可找回性——落點重命名（US1）、章節切分（US2）、每章動作（US3）。"""

import json
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_HIST = [{"role": "user", "content": "開頭談 A"},
         {"role": "assistant", "content": "……最後落在 B_四元樹"}]


class TestRetitle(unittest.TestCase):
    def test_new_save_reflects_landing(self):               # T003 標題反映落點
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "B_四元樹的由來"     # 注入：反映落點
        TestClient(app).post("/chat/save", data={"history": json.dumps(_HIST)},
                             follow_redirects=True)
        convs = Repository(db).list_conversations()
        self.assertEqual(convs[0].title, "B_四元樹的由來")

    def test_manual_rename(self):                           # T003 手動改名
        db = temp_db()
        Repository(db).close()
        repo = Repository(db)
        cid = repo.save_conversation("舊標題", _HIST, None)
        repo.close()
        app = build_app(db)
        TestClient(app).post(f"/conversations/{cid}/rename",
                             data={"title": "我自己取的名字"}, follow_redirects=True)
        self.assertEqual(Repository(db).get_conversation(cid).title, "我自己取的名字")

    def test_retitle_existing(self):                        # T003 既有可重生
        db = temp_db()
        Repository(db).close()
        repo = Repository(db)
        cid = repo.save_conversation("Flow Matching", _HIST, None)
        repo.close()
        app = build_app(db)
        app.state.title_factory = lambda m: "重生：落點 B"
        TestClient(app).post(f"/conversations/{cid}/retitle", follow_redirects=True)
        self.assertEqual(Repository(db).get_conversation(cid).title, "重生：落點 B")

    def test_title_failure_falls_back(self):                # T003 標題失敗退回不崩
        db = temp_db()
        app = build_app(db)
        def boom(m):
            raise RuntimeError("LLM 掛了")
        app.state.title_factory = boom
        r = TestClient(app).post("/chat/save", data={"history": json.dumps(_HIST)},
                                 follow_redirects=True)
        self.assertEqual(r.status_code, 200)                # 不崩
        self.assertEqual(len(Repository(db).list_conversations()), 1)  # 仍存下

    def test_view_does_not_change_title(self):              # T003 檢視不自動改
        db = temp_db()
        Repository(db).close()
        repo = Repository(db)
        cid = repo.save_conversation("原標題", _HIST, None)
        repo.close()
        app = build_app(db)
        TestClient(app).get(f"/conversations/{cid}")
        self.assertEqual(Repository(db).get_conversation(cid).title, "原標題")


def _seg_stub(n_first_end):
    """回一個 segment_factory：把對話切成 2 章（第 1..k / k+1..end）。"""
    def _f(messages):
        n = len(messages)
        from knowfield.chat.capture import normalize_chapters
        raw = [{"title": "前半章", "start": 1, "summary": "s1"},
               {"title": "後半章", "start": n_first_end + 1, "summary": "s2"}]
        return normalize_chapters(raw, n)
    return _f


class TestSegment(unittest.TestCase):
    def _seed(self, db, n=6):
        repo = Repository(db)
        msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
                for i in range(n)]
        cid = repo.save_conversation("長對話", msgs, None)
        repo.close()
        return cid

    def test_segment_renders_chapters(self):                # T007
        db = temp_db()
        Repository(db).close()
        cid = self._seed(db, 6)
        app = build_app(db)
        app.state.segment_factory = _seg_stub(3)
        r = TestClient(app).post(f"/conversations/{cid}/segment")
        self.assertEqual(r.status_code, 200)
        self.assertIn("前半章", r.text)
        self.assertIn("後半章", r.text)

    def test_segment_does_not_persist(self):                # T007 不落庫守衛
        db = temp_db()
        Repository(db).close()
        cid = self._seed(db, 6)
        app = build_app(db)
        app.state.segment_factory = _seg_stub(3)
        TestClient(app).post(f"/conversations/{cid}/segment")
        conv = Repository(db).get_conversation(cid)
        self.assertEqual(conv.title, "長對話")               # 標題未變
        self.assertEqual(len(conv.messages), 6)              # 訊息未變

    def test_segment_failure_falls_back(self):              # T006/T007 失敗退整段
        db = temp_db()
        Repository(db).close()
        cid = self._seed(db, 6)
        app = build_app(db)
        def boom(m):
            raise RuntimeError("切不出")
        app.state.segment_factory = boom
        r = TestClient(app).post(f"/conversations/{cid}/segment")
        self.assertEqual(r.status_code, 200)                # 不崩


class TestChapterActions(unittest.TestCase):
    def _seed(self, db, n=6):
        repo = Repository(db)
        msgs = [{"role": "user", "content": f"訊息{i}"} for i in range(n)]
        cid = repo.save_conversation("t", msgs, None)
        repo.close()
        return cid

    def test_chapter_export_range(self):                    # T009 每章匯出只含該章
        db = temp_db()
        Repository(db).close()
        cid = self._seed(db, 6)
        app = build_app(db)
        r = TestClient(app).get(f"/conversations/{cid}/export?as=md&from=1&to=2")
        self.assertIn("訊息0", r.text)
        self.assertIn("訊息1", r.text)
        self.assertNotIn("訊息5", r.text)                    # 範圍外不在

    def test_chapter_distill_no_auto_anoint(self):          # T009 整理這章不自動冊封
        db = temp_db()
        Repository(db).close()
        cid = self._seed(db, 6)
        app = build_app(db)
        app.state.distill_factory = lambda hist: []          # 注入：出候選（此處空）
        TestClient(app).post(f"/conversations/{cid}/distill?from=1&to=3",
                             follow_redirects=True)
        self.assertEqual(len(Repository(db).list_why_nodes()), 0)  # 不自動冊封


if __name__ == "__main__":
    unittest.main()
