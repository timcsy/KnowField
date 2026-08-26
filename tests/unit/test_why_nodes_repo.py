"""T008/T009 [US2/US3]：why_nodes CRUD＋已冊封 UNION 進 corpus（負 id、source_class=root）。"""

import unittest

from knowfield.store.repository import Repository
from tests.rag_helpers import temp_db


class TestWhyNodesRepo(unittest.TestCase):
    def _repo(self):
        return Repository(temp_db())

    def test_add_list_anoint_delete(self):
        repo = self._repo()
        wid = repo.add_why_node(claim="因為直接建模長程依賴",
                                evidence_urls=["https://a/1"],
                                touchstones=[{"name": "機制", "passed": True}],
                                fog_flag=False, source_entry_id=5, created_at="2026-07-25")
        cands = repo.list_why_nodes(status="candidate")
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].claim, "因為直接建模長程依賴")

        self.assertTrue(repo.anoint_why_node(wid, claim="因為直接建模長程依賴（修訂）"))
        anointed = repo.list_why_nodes(status="anointed")
        self.assertEqual(len(anointed), 1)
        self.assertIn("修訂", anointed[0].claim)
        self.assertEqual(repo.list_why_nodes(status="candidate"), [])

        self.assertTrue(repo.delete_why_node(wid))
        self.assertEqual(repo.list_why_nodes(), [])
        repo.close()

    def test_ladder_round_trips(self):
        repo = self._repo()
        wid = repo.add_why_node("aha", ["https://a/1"], [], False, 1, "2026-07-25",
                                ladder=["表面", "更深", "bedrock"])
        w = repo.list_why_nodes()[0]
        self.assertEqual(w.ladder, ["表面", "更深", "bedrock"])
        self.assertEqual(wid, w.id)
        repo.close()

    def test_anointed_enters_corpus_candidate_does_not(self):
        repo = self._repo()
        cand = repo.add_why_node("候選根因", ["https://a/c"], [], False, 1, "2026-07-25")
        anoint = repo.add_why_node("已冊封根因", ["https://a/an"], [], False, 2, "2026-07-25",
                                   ladder=["表面 why", "bedrock：資訊理論極限"])
        repo.anoint_why_node(anoint)

        corpus = repo.list_corpus_entries()
        roots = [e for e in corpus if e.source_class == "root"]
        self.assertEqual(len(roots), 1)                       # 只有已冊封進 corpus
        self.assertIn("已冊封根因", roots[0].body)             # 主張
        self.assertIn("資訊理論極限", roots[0].body)           # 階梯也進檢索（deep why 可撈）
        self.assertLess(roots[0].entry_id, 0)                 # 負 id 避碰撞
        self.assertEqual(roots[0].url, "https://a/an")        # 證據 url
        self.assertNotIn("候選根因", [e.body for e in corpus])  # 候選不進
        repo.close()

    def test_archive_keeps_the_vector_but_erase_clears_it(self):
        """⚠️ spec 056 起分兩段：**封存不清向量，抹除才清**。

        原本這條斷言「刪 why-node 就清向量」。封存時清它是**多餘的**
        （檢索一律先過 `list_corpus_entries`，那裡已經濾掉封存的），
        而且**弄壞復原**——復原後向量沒了、要重算一次 API，還不會報錯。
        真正不該留幽靈向量的時機是**抹除**：內容都不在了。
        """
        repo = self._repo()
        wid = repo.add_why_node("x", ["https://a/1"], [], False, 1, "2026-07-25")
        repo.anoint_why_node(wid)
        repo.conn.execute("INSERT INTO entry_embeddings (entry_id, tag, dim, vector_json)"
                          " VALUES (%s,%s,%s,%s)", (-wid, "hashing-256", 1, "[0.1]"))
        repo.conn.commit()
        left = lambda: repo.conn.execute(
            "SELECT COUNT(*) c FROM entry_embeddings WHERE entry_id=%s", (-wid,)).fetchone()["c"]

        repo.delete_why_node(wid, "2026-08-26T10:00:00Z")      # 封存
        self.assertEqual(left(), 1, "封存清掉了向量——復原之後檢索就找不到它了")

        repo.erase_knowledge("why_node", wid, "2026-08-26T11:00:00Z")   # 抹除
        self.assertEqual(left(), 0, "抹除沒清向量——內容不在了，那是幽靈")
        repo.close()


if __name__ == "__main__":
    unittest.main()
