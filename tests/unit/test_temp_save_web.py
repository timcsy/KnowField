"""spec 028：暫時存檔（自動 upsert）＋TTL 懶清＋升永久（人閘門）＋不注入回場守衛。"""

import json
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from learnnews.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_H1 = [{"role": "user", "content": "第一句"}]
_H2 = [{"role": "user", "content": "第一句"}, {"role": "assistant", "content": "答一"},
       {"role": "user", "content": "第二句"}]


def _iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


class TestAutosave(unittest.TestCase):
    def test_upsert_one_row(self):                          # T005 逐輪 upsert 一筆
        db = temp_db()
        app = build_app(db)
        c = TestClient(app)
        r1 = c.post("/chat/autosave", data={"history": json.dumps(_H1), "temp_id": ""})
        tid = r1.json()["temp_id"]
        self.assertTrue(tid)
        c.post("/chat/autosave", data={"history": json.dumps(_H2), "temp_id": str(tid)})
        c.post("/chat/autosave", data={"history": json.dumps(_H2), "temp_id": str(tid)})
        repo = Repository(db)
        convs = repo.list_conversations()
        self.assertEqual(len(convs), 1)                     # 只 1 筆
        self.assertTrue(convs[0].temporary)                 # 暫存
        self.assertEqual(len(convs[0].messages), 3)         # 更新為最新
        repo.close()

    def test_empty_no_save(self):                           # T005 空不存
        db = temp_db()
        app = build_app(db)
        r = TestClient(app).post("/chat/autosave", data={"history": "[]", "temp_id": ""})
        self.assertIsNone(r.json().get("temp_id"))
        self.assertEqual(len(Repository(db).list_conversations()), 0)


class TestLazyPurge(unittest.TestCase):
    def test_purge_expired_only(self):                      # T008 懶清只刪過期暫存
        db = temp_db()
        Repository(db).close()
        repo = Repository(db)
        # 過期暫存（8 天前）
        repo.conn.execute(
            "INSERT INTO conversations (title, messages, temporary, last_activity_at, created_at)"
            " VALUES ('過期暫存','[]',1,?,?)", (_iso(8), _iso(8)))
        # 新暫存（今天）
        repo.conn.execute(
            "INSERT INTO conversations (title, messages, temporary, last_activity_at, created_at)"
            " VALUES ('新暫存','[]',1,?,?)", (_iso(0), _iso(0)))
        # 永久（很舊）
        repo.conn.execute(
            "INSERT INTO conversations (title, messages, temporary, last_activity_at, created_at)"
            " VALUES ('永久','[]',0,?,?)", (_iso(99), _iso(99)))
        repo.conn.commit()
        repo.close()
        app = build_app(db)
        TestClient(app).get("/conversations")               # 載入時懶清
        titles = [c.title for c in Repository(db).list_conversations()]
        self.assertNotIn("過期暫存", titles)                # 過期暫存被刪
        self.assertIn("新暫存", titles)                     # 新暫存留
        self.assertIn("永久", titles)                       # 永久留


class TestPromote(unittest.TestCase):
    def test_save_promotes_temp(self):                      # T010 存這段→升永久同一筆
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "落點標題"
        c = TestClient(app)
        tid = c.post("/chat/autosave", data={"history": json.dumps(_H2),
                                             "temp_id": ""}).json()["temp_id"]
        c.post("/chat/save", data={"history": json.dumps(_H2), "temp_id": str(tid)},
               follow_redirects=True)
        repo = Repository(db)
        convs = repo.list_conversations()
        self.assertEqual(len(convs), 1)                     # 不新增
        self.assertFalse(convs[0].temporary)               # 升永久
        self.assertEqual(convs[0].title, "落點標題")        # 生落點標題
        repo.close()

    def test_promote_route(self):                           # T010 轉永久鈕
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "落點X"
        c = TestClient(app)
        tid = c.post("/chat/autosave", data={"history": json.dumps(_H2),
                                             "temp_id": ""}).json()["temp_id"]
        c.post(f"/conversations/{tid}/promote", follow_redirects=True)
        self.assertFalse(Repository(db).get_conversation(tid).temporary)

    def test_anoint_all_share_one_conversation(self):       # 全部精選：多條候選連同存→共用一份由來
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "共用由來"
        c = TestClient(app)
        tid = c.post("/chat/autosave", data={"history": json.dumps(_H2),
                                             "temp_id": ""}).json()["temp_id"]
        for claim in ("根因A", "根因B", "根因C"):             # 逐條精選（＝前端「全部精選」批次做的事）
            c.post("/chat/anoint", data={"claim": claim, "ladder": "", "evidence_urls": "",
                                         "save_convo": "1", "history": json.dumps(_H2),
                                         "temp_id": str(tid)}, follow_redirects=True)
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), 1)         # 只一份對話（去重＋同筆升永久）
        anointed = repo.list_why_nodes("anointed")
        self.assertEqual(len(anointed), 3)                          # 三條都精選
        cids = {repo.why_node_provenance().get(n.id) for n in anointed}
        self.assertEqual(len(cids), 1)                              # 三條都連到同一份由來
        self.assertEqual(next(iter(cids)), int(tid))
        repo.close()

    def test_anoint_promotes_temp_and_links(self):          # T010 冊封連同存→升永久＋連根因
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "由來標題"
        c = TestClient(app)
        tid = c.post("/chat/autosave", data={"history": json.dumps(_H2),
                                             "temp_id": ""}).json()["temp_id"]
        c.post("/chat/anoint", data={"claim": "根因A", "ladder": "", "evidence_urls": "",
                                     "save_convo": "1", "history": json.dumps(_H2),
                                     "temp_id": str(tid)}, follow_redirects=True)
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), 1)          # 同一筆、不新增
        self.assertFalse(repo.get_conversation(tid).temporary)      # 升永久
        anointed = repo.list_why_nodes("anointed")
        self.assertEqual(repo.why_node_provenance().get(anointed[0].id), tid)  # 連到它
        repo.close()


class TestGuardNotInjected(unittest.TestCase):
    def test_temporary_not_in_field_prompt(self):           # T011 暫存不注入回場（原則 6）
        db = temp_db()
        app = build_app(db)
        secret = "SECRET_FANTASY_暫存不該進場"
        TestClient(app).post("/chat/autosave", data={
            "history": json.dumps([{"role": "user", "content": secret}]), "temp_id": ""})
        from learnnews.chat.field_chat import build_field_system_prompt
        repo = Repository(db)
        roots = repo.list_why_nodes("anointed")
        repo.close()
        self.assertNotIn(secret, build_field_system_prompt(roots))


if __name__ == "__main__":
    unittest.main()
