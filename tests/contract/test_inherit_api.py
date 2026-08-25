"""契約：出生就歸位（spec 051）——四條出生路徑各走一次真的請求。

⚠️ 單元測試證明 `place_new` 算得對；這裡證明**它真的被叫到了**，
而且是在**連結建好之後**叫的。少了這層，`place_new` 可以完全正確而系統完全沒歸位。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_M = [{"role": "user", "content": "問題"}, {"role": "assistant", "content": "答案"}]


def _domains(db):
    repo = Repository(db)
    ai = repo.create_domain("AI")
    gen = repo.create_domain("生成模型", ai)
    repo.close()
    return ai, gen


class TestInheritApi(unittest.TestCase):
    def test_anoint_inherits_the_conversation_not_the_request(self):
        """⚠️ 這條**刻意不送 `domain_id`**——不然它會被 `current` 的退路餵飽，
        測起來全綠而繼承根本沒發生（第一版就是這樣，攻擊打不到）。

        同時在守**呼叫順序**：對話是在冊封之後才連上去的。
        """
        db = temp_db(); ai, gen = _domains(db)
        cl = TestClient(build_app(db))
        # 先有一段**已經歸位**的暫存對話
        av = cl.post("/api/chat/autosave",
                     json={"history": _M, "domain_id": gen}).json()
        tid = av.get("temp_id") or av.get("id")
        self.assertTrue(tid, f"autosave 沒回 id：{av}")
        r = cl.post("/api/chat/anoint", json={"claim": "某條理解", "save_convo": True,
                                              "history": _M, "temp_id": str(tid)}).json()
        self.assertEqual(r["status"], "created")
        repo = Repository(db)
        w = repo.list_why_nodes("anointed")[0]
        self.assertEqual(repo.knowledge_domain("why_node", w.id), gen,
                         "沒有繼承到那段對話的領域")
        repo.close()

    def test_a_conversation_born_at_anoint_time_is_also_placed(self):
        """沒有暫存時 `save_conversation` 會**新建**一段——它自己也是剛出生的葉節點。"""
        db = temp_db(); ai, gen = _domains(db)
        cl = TestClient(build_app(db))
        cl.post("/api/chat/anoint", json={"claim": "理解", "save_convo": True,
                                          "history": _M, "domain_id": gen})
        repo = Repository(db)
        cs = repo.list_conversations()
        self.assertEqual([c.domain_id for c in cs], [gen], "新建的對話留在根領域")
        repo.close()

    def test_anoint_without_a_conversation_uses_where_you_stand(self):
        db = temp_db(); ai, gen = _domains(db)
        cl = TestClient(build_app(db))
        cl.post("/api/chat/anoint", json={"claim": "沒有對話的理解", "domain_id": gen})
        repo = Repository(db)
        w = repo.list_why_nodes("anointed")[0]
        self.assertEqual(repo.knowledge_domain("why_node", w.id), gen)
        repo.close()

    def test_anoint_at_root_stays_at_root(self):
        db = temp_db(); _domains(db)
        cl = TestClient(build_app(db))
        cl.post("/api/chat/anoint", json={"claim": "在根領域收的", "history": _M})
        repo = Repository(db)
        w = repo.list_why_nodes("anointed")[0]
        self.assertIsNone(repo.knowledge_domain("why_node", w.id))
        repo.close()

    def test_saved_article_inherits_its_roots(self):
        db = temp_db(); ai, gen = _domains(db)
        repo = Repository(db)
        r = repo.conn.execute(
            "INSERT INTO why_nodes (claim, kind, status, domain_id)"
            " VALUES ('理解','推論','anointed',%s) RETURNING id", (gen,)).fetchone()
        w = int(r["id"]); repo.conn.commit(); repo.close()
        cl = TestClient(build_app(db))
        aid = cl.post("/api/article/save", json={"topic": "t", "title": "標題",
                                                 "markdown": "內文", "root_ids": [w]}).json()["id"]
        repo = Repository(db)
        self.assertEqual(repo.knowledge_domain("article", aid), gen)
        self.assertEqual(repo.article_roots(aid), [w], "⚠️ 連結沒存的話，繼承是靠運氣")
        repo.close()

    def test_article_with_no_roots_uses_where_you_stand(self):
        db = temp_db(); ai, gen = _domains(db)
        cl = TestClient(build_app(db))
        aid = cl.post("/api/article/save", json={"topic": "t", "title": "標題",
                                                 "markdown": "內文",
                                                 "domain_id": gen}).json()["id"]
        repo = Repository(db)
        self.assertEqual(repo.knowledge_domain("article", aid), gen)
        repo.close()

    def test_whynode_anoint_endpoint_also_places(self):
        """來源側／候選側走的是另一支端點——⚠️ 只接一支就會有一半的知識繼續漏掉。"""
        db = temp_db(); ai, gen = _domains(db)
        repo = Repository(db)
        wid = repo.add_why_node("候選理解", [], [], False, 0, "2026-08-26T00:00:00Z")
        repo.close()
        TestClient(build_app(db)).post("/api/whynode/anoint",
                                       json={"id": wid, "domain_id": gen})
        repo = Repository(db)
        self.assertEqual(repo.knowledge_domain("why_node", wid), gen)
        repo.close()


if __name__ == "__main__":
    unittest.main()
