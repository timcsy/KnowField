"""spec 028：暫時存檔（自動 upsert）＋TTL 懶清＋升永久（人閘門）＋不注入回場守衛。

re-platform 退場（階段 27 里程碑五）：舊 Jinja 路由已退役，改走 /api（行為同一份服務閉包）。
"""

import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
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
        c = TestClient(build_app(db))
        tid = c.post("/api/chat/autosave", json={"history": _H1, "temp_id": None}).json()["temp_id"]
        self.assertTrue(tid)
        c.post("/api/chat/autosave", json={"history": _H2, "temp_id": tid})
        c.post("/api/chat/autosave", json={"history": _H2, "temp_id": tid})
        repo = Repository(db)
        convs = repo.list_conversations()
        self.assertEqual(len(convs), 1)                     # 只 1 筆
        self.assertEqual(len(convs[0].messages), 3)         # 更新為最新
        repo.close()

    def test_empty_no_save(self):                           # T005 空不存
        db = temp_db()
        r = TestClient(build_app(db)).post("/api/chat/autosave", json={"history": [], "temp_id": None})
        self.assertIsNone(r.json().get("temp_id"))
        self.assertEqual(len(Repository(db).list_conversations()), 0)

    def test_autosave_updates_permanent_in_place(self):     # 接回已存檔對話繼續聊→就地更新、不另開暫存
        repo = Repository(temp_db())
        cid = repo.save_conversation("存檔的", [{"role": "user", "content": "一"}], None)  # 永久
        ret = repo.autosave_temporary(
            cid, [{"role": "user", "content": "一"}, {"role": "assistant", "content": "二"}],
            "2026-08-08T00:00:00Z")
        self.assertEqual(ret, cid)                          # 回同一筆、不新建
        self.assertEqual(len(repo.list_conversations()), 1) # 沒另開暫存
        c = repo.get_conversation(cid)
        self.assertEqual(len(c.messages), 2)                # 訊息就地更新
        repo.close()


class TestDeleteConversation(unittest.TestCase):
    def test_delete_unreferenced(self):                     # 無核心理解引用→可刪
        repo = Repository(temp_db())
        cid = repo.save_conversation("刪我", [{"role": "user", "content": "hi"}], None)
        self.assertEqual(repo.conversation_referrers(cid), [])
        self.assertTrue(repo.delete_conversation(cid))
        # spec 055：這是**封存**——離開活清單，但遺骸還在（「刪除又要不能不見」）
        self.assertNotIn(cid, [c.id for c in repo.list_conversations()])
        repo.close()

    def test_referenced_blocks_delete(self):                # 被核心理解引用（由來）→擋刪，回 blocked_by（護溯源）
        db = temp_db()
        repo = Repository(db)
        wid = repo.add_why_node("根因甲", [], [], False, 0, "2026")
        cid = repo.save_conversation("由來", [{"role": "user", "content": "x"}], wid)  # 連到 why_node
        refs = repo.conversation_referrers(cid)
        self.assertEqual([r["claim"] for r in refs], ["根因甲"])
        repo.close()
        r = TestClient(build_app(db)).post(f"/api/conversations/{cid}/delete").json()
        self.assertFalse(r["deleted"])
        self.assertIn("根因甲", r["blocked_by"])
        self.assertIsNotNone(Repository(db).get_conversation(cid))   # 沒被刪


# ⚠️ spec 040：TestLazyPurge 連同「依時間清理過期暫存」的機制一起移除。
# 移除的是機制不是資料——舊暫存全數保留為一般對話（history/097）。

class TestSaveAndLink(unittest.TestCase):
    def test_save_names_conversation(self):                 # spec 040：存這段＝給它名字（同一筆、不新增）
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "落點標題"
        c = TestClient(app)
        tid = c.post("/api/chat/autosave", json={"history": _H2, "temp_id": None}).json()["temp_id"]
        c.post("/api/chat/save", json={"history": _H2, "temp_id": tid})
        repo = Repository(db)
        convs = repo.list_conversations()
        self.assertEqual(len(convs), 1)                     # 不新增
        self.assertEqual(convs[0].title, "落點標題")        # 生落點標題
        repo.close()

    def test_save_route_sets_title(self):                   # spec 040：該路由現在只設標題
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "落點X"
        c = TestClient(app)
        tid = c.post("/api/chat/autosave", json={"history": _H2, "temp_id": None}).json()["temp_id"]
        c.post(f"/api/conversations/{tid}/promote")

    def test_anoint_all_share_one_conversation(self):       # 全部精選：多條候選連同存→共用一份由來
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "共用由來"
        c = TestClient(app)
        tid = c.post("/api/chat/autosave", json={"history": _H2, "temp_id": None}).json()["temp_id"]
        for claim in ("根因A", "根因B", "根因C"):             # 逐條精選（＝前端「全部精選」批次做的事）
            c.post("/api/chat/anoint", json={"claim": claim, "ladder": "", "evidence_urls": "",
                                             "save_convo": True, "history": _H2, "temp_id": tid})
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), 1)         # 只一份對話（去重＋同筆升永久）
        anointed = repo.list_why_nodes("anointed")
        self.assertEqual(len(anointed), 3)                          # 三條都精選
        cids = {repo.why_node_provenance().get(n.id) for n in anointed}
        self.assertEqual(len(cids), 1)                              # 三條都連到同一份由來
        self.assertEqual(next(iter(cids)), int(tid))
        repo.close()

    def test_anoint_links_conversation(self):               # 冊封連同存→同一筆＋連根因
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "由來標題"
        c = TestClient(app)
        tid = c.post("/api/chat/autosave", json={"history": _H2, "temp_id": None}).json()["temp_id"]
        c.post("/api/chat/anoint", json={"claim": "根因A", "ladder": "", "evidence_urls": "",
                                         "save_convo": True, "history": _H2, "temp_id": tid})
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), 1)          # 同一筆、不新增
        anointed = repo.list_why_nodes("anointed")
        self.assertEqual(repo.why_node_provenance().get(anointed[0].id), tid)  # 連到它
        repo.close()


class TestGuardNotInjected(unittest.TestCase):
    def test_temporary_not_in_field_prompt(self):           # T011 暫存不注入回場（原則 6）
        db = temp_db()
        secret = "SECRET_FANTASY_暫存不該進場"
        TestClient(build_app(db)).post("/api/chat/autosave", json={
            "history": [{"role": "user", "content": secret}], "temp_id": None})
        from knowfield.chat.field_chat import build_field_system_prompt
        repo = Repository(db)
        roots = repo.list_why_nodes("anointed")
        repo.close()
        self.assertNotIn(secret, build_field_system_prompt(roots))


if __name__ == "__main__":
    unittest.main()
