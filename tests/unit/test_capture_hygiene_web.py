"""spec 025：去重（同段多根因共用一份）＋收尾提醒＋spec023 不回歸＋人閘門守衛。"""

import json
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

_HIST = [{"role": "user", "content": "attention 為何加權？"},
         {"role": "assistant", "content": "內容決定權重。"}]
_HIST2 = [{"role": "user", "content": "完全不同的一段對話"},
          {"role": "assistant", "content": "另一個主題。"}]


def _anoint(client, claim, history, save=True):
    data = {"claim": claim, "ladder": "階梯一行", "evidence_urls": "", "history": json.dumps(history)}
    if save:
        data["save_convo"] = "1"
    client.post("/chat/anoint", data=data, follow_redirects=True)


class TestDedup(unittest.TestCase):
    def test_same_conversation_shares_one(self):            # T005 同段共用一份
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "由來標題"
        c = TestClient(app)
        for claim in ("根因A", "根因B", "根因C"):
            _anoint(c, claim, _HIST)
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), 1)         # 只一份
        prov = repo.why_node_provenance()
        anointed = repo.list_why_nodes("anointed")
        self.assertEqual(len(anointed), 3)
        cids = {prov[w.id] for w in anointed}
        self.assertEqual(len(cids), 1)                              # 三條映同一 cid
        repo.close()

    def test_different_conversation_not_merged(self):       # T005 異段不誤併
        db = temp_db()
        app = build_app(db)
        app.state.title_factory = lambda m: "t"
        c = TestClient(app)
        _anoint(c, "A", _HIST)
        _anoint(c, "B", _HIST2)
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), 2)         # 兩份
        repo.close()

    def test_anoint_without_save_no_conversation(self):     # T005 不連同存→不增
        db = temp_db()
        app = build_app(db)
        c = TestClient(app)
        _anoint(c, "只冊封", _HIST, save=False)
        repo = Repository(db)
        self.assertEqual(len(repo.list_conversations()), 0)
        repo.close()


class TestSpec023NoRegress(unittest.TestCase):
    def test_provenance_and_delete(self):                   # T006
        db = temp_db()
        Repository(db).close()                              # init
        repo = Repository(db)
        wid = repo.add_why_node("c", [], [], False, 0, "2026-07-29T00:00:00Z", ladder=["x"])
        repo.anoint_why_node(wid)
        cid = repo.save_conversation("t", _HIST, wid)
        self.assertEqual(repo.why_node_provenance().get(wid), cid)  # 連得上
        repo.delete_why_node(wid)
        self.assertNotIn(wid, repo.why_node_provenance())          # 刪根因→不再含
        self.assertEqual(len(repo.list_conversations()), 1)        # 對話仍在（不孤兒）
        repo.close()

    def test_save_twice_same_dedup(self):                   # T010 去重不刪改既有
        db = temp_db()
        Repository(db).close()
        repo = Repository(db)
        cid1 = repo.save_conversation("t", _HIST, None)
        cid2 = repo.save_conversation("t", _HIST, None)     # 同段再存
        self.assertEqual(cid1, cid2)                        # 回既有、不新增
        self.assertEqual(len(repo.list_conversations()), 1)
        repo.close()


class TestDistillNudge(unittest.TestCase):
    def _long(self, n):
        return [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
                for i in range(n)]

    def test_long_uncaptured_shows_nudge(self):             # T008
        db = temp_db()
        app = build_app(db)
        c = TestClient(app)
        r = c.post("/chat", data={"history": json.dumps(self._long(40)),
                                  "message": "", "last_captured": "2"})
        self.assertIn("尾段", r.text)                       # 出現「尾段未收」提醒

    def test_short_no_nudge(self):                          # T008
        db = temp_db()
        app = build_app(db)
        c = TestClient(app)
        r = c.post("/chat", data={"history": json.dumps(self._long(4)),
                                  "message": "", "last_captured": "0"})
        self.assertNotIn("尾段", r.text)

    def test_recently_captured_no_nudge(self):              # T008 剛收→不吵
        db = temp_db()
        app = build_app(db)
        c = TestClient(app)
        r = c.post("/chat", data={"history": json.dumps(self._long(40)),
                                  "message": "", "last_captured": "39"})
        self.assertNotIn("尾段", r.text)

    def test_nudge_does_not_auto_anoint(self):              # T008/T010 守衛
        db = temp_db()
        app = build_app(db)
        c = TestClient(app)
        c.post("/chat", data={"history": json.dumps(self._long(40)),
                              "message": "", "last_captured": "2"})
        repo = Repository(db)
        self.assertEqual(len(repo.list_why_nodes()), 0)     # 看頁不自動冊封
        self.assertEqual(len(repo.list_conversations()), 0)
        repo.close()


if __name__ == "__main__":
    unittest.main()
