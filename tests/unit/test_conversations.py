"""spec 023：對話的「由來」存檔——repository（save/list/get/provenance、刪根因不崩）。"""

import unittest

from learnnews.store.repository import Repository
from tests.rag_helpers import temp_db


def _repo():
    return Repository(temp_db())


class TestConversationRepo(unittest.TestCase):
    def test_save_list_get(self):                                # T002
        repo = _repo()
        msgs = [{"role": "user", "content": "問"},
                {"role": "assistant", "content": "答", "sources": [{"n": 1, "url": "https://a/1"}]}]
        cid = repo.save_conversation("由來標題", msgs, None)
        got = repo.get_conversation(cid)
        self.assertEqual(got.title, "由來標題")
        self.assertEqual(got.messages, msgs)                     # 整段（含 sources）取回
        self.assertIsNone(got.why_node_id)
        self.assertEqual(len(repo.list_conversations()), 1)
        repo.close()

    def test_list_newest_first(self):                            # T002
        repo = _repo()
        a = repo.save_conversation("舊", [], None)
        b = repo.save_conversation("新", [], None)
        ids = [c.id for c in repo.list_conversations()]
        self.assertEqual(ids[0], b)                              # 新到舊
        self.assertEqual(ids[1], a)
        repo.close()

    def test_provenance_map(self):                               # T002
        repo = _repo()
        wid = repo.add_why_node("根因", [], [], False, 0, "2026-07-29", ladder=["階"])
        repo.anoint_why_node(wid)
        cid = repo.save_conversation("由來", [{"role": "user", "content": "x"}], wid)
        prov = repo.why_node_provenance()
        self.assertEqual(prov.get(wid), cid)                     # {根因: 對話}
        repo.close()

    def test_delete_whynode_does_not_orphan_crash(self):         # T003（刪根因不崩）
        repo = _repo()
        wid = repo.add_why_node("根因", [], [], False, 0, "2026-07-29", ladder=["階"])
        repo.anoint_why_node(wid)
        cid = repo.save_conversation("由來", [{"role": "user", "content": "x"}], wid)
        repo.delete_why_node(wid)
        self.assertEqual(len(repo.list_conversations()), 1)      # 對話仍在（獨立）
        self.assertNotIn(wid, repo.why_node_provenance())        # 不再連得到、不崩
        self.assertIsNotNone(repo.get_conversation(cid))         # 讀得到
        repo.close()


if __name__ == "__main__":
    unittest.main()
