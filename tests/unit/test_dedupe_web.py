"""spec 026：既有重複對話清理——預覽唯讀（人閘門）＋執行（重指＋刪、非破壞）。"""

import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


def _seed(db, groups):
    """groups: list of (content, 份數, [連的根因 claim...])。回 repo。"""
    repo = Repository(db)
    for content, n, claims in groups:
        msgs = [{"role": "user", "content": content}]
        # 各份存成獨立對話（why_node_id None），再各連一根因
        for i in range(n):
            # 直接插入避免 save_conversation 去重（模擬既有複本）
            import json
            repo.conn.execute(
                "INSERT INTO conversations (title, messages, why_node_id, created_at)"
                " VALUES (?,?,?,?)", (content, json.dumps(msgs), None, "2026-07-30T00:00:00Z"))
        repo.conn.commit()
        # 為此組每份各連一根因
        cids = [r["id"] for r in repo.conn.execute(
            "SELECT id FROM conversations WHERE title=? ORDER BY id", (content,)).fetchall()]
        for claim, cid in zip(claims, cids):
            wid = repo.add_why_node(claim, [], [], False, 0, "2026-07-30", ladder=["階"])
            repo.anoint_why_node(wid)
            repo.conn.execute("UPDATE why_nodes SET conversation_id=? WHERE id=?", (cid, wid))
        repo.conn.commit()
    repo.close()


class TestPreview(unittest.TestCase):
    def test_preview_reports_and_no_change(self):           # T003 人閘門守衛
        db = temp_db()
        Repository(db).close()
        _seed(db, [("A組", 3, ["a1", "a2", "a3"]), ("B組", 1, ["b1"])])
        app = build_app(db)
        c = TestClient(app)
        before = len(Repository(db).list_conversations())
        r = c.get("/conversations/dedupe")
        self.assertEqual(r.status_code, 200)
        self.assertIn("1", r.text)              # 1 組重複
        self.assertIn("重複", r.text)
        # GET 不動資料
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), before)  # 份數不變
        self.assertEqual(len(repo.list_conversations()), 4)
        repo.close()

    def test_preview_no_dup_friendly(self):                 # T003 無重複
        db = temp_db()
        Repository(db).close()
        _seed(db, [("X", 1, ["x"]), ("Y", 1, ["y"])])
        app = build_app(db)
        r = TestClient(app).get("/conversations/dedupe")
        self.assertIn("沒有重複", r.text)


class TestExecute(unittest.TestCase):
    def test_execute_merges_and_repoints(self):             # T005/T007
        db = temp_db()
        Repository(db).close()
        # A 組 3 份同內容各連根因；C 組 2 份異內容（不同 content→異指紋）
        _seed(db, [("A組", 3, ["a1", "a2", "a3"]),
                   ("C1", 1, ["c1"]), ("C2", 1, ["c2"])])
        app = build_app(db)
        c = TestClient(app)
        repo = Repository(db)
        a_cids = sorted(x.id for x in repo.list_conversations() if x.title == "A組")
        survivor = max(a_cids)
        claim_before = {w.id: w.claim for w in repo.list_why_nodes("anointed")}
        repo.close()

        r = c.post("/conversations/dedupe", follow_redirects=False)
        self.assertIn(r.status_code, (302, 303))

        repo = Repository(db)
        titles = [x.title for x in repo.list_conversations()]
        self.assertEqual(titles.count("A組"), 1)             # A 組只剩 1 份
        self.assertEqual(titles.count("C1") + titles.count("C2"), 2)  # 異指紋兩份都在
        # A 組 3 根因皆重指 survivor
        prov = repo.why_node_provenance()
        a_roots = [w.id for w in repo.list_why_nodes("anointed")
                   if w.claim in ("a1", "a2", "a3")]
        for wid in a_roots:
            self.assertEqual(prov.get(wid), survivor)        # 皆連 survivor（不斷、不孤兒）
        # 根因主張未變、根因總數不變
        claim_after = {w.id: w.claim for w in repo.list_why_nodes("anointed")}
        self.assertEqual(claim_before, claim_after)
        repo.close()

    def test_execute_empty_friendly(self):                  # T005 空庫
        db = temp_db()
        Repository(db).close()
        app = build_app(db)
        r = TestClient(app).post("/conversations/dedupe", follow_redirects=True)
        self.assertEqual(r.status_code, 200)                # 不崩
        self.assertEqual(len(Repository(db).list_conversations()), 0)


if __name__ == "__main__":
    unittest.main()
