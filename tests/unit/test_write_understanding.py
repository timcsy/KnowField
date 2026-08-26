"""spec 062：人自己寫理解。

⚠️ 這一刀最容易安靜壞掉的是 **FR-005**：寫進去了、清單看得到、
但**沒進檢索語料** ⇒ 那條理解不在你的場裡，而畫面上一切正常。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class WriteUnderstandingBase(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)

    def repo(self):
        return Repository(self.db)

    def write(self, **kw):
        body = {"claim": "測試主張", "kind": "推論"}
        body.update(kw)
        return self.c.post("/api/understanding/write", json=body)


class TestSourceRequired(WriteUnderstandingBase):
    """FR-002／FR-003：出處必填，而且是**擋住**不是警告。"""

    def test_no_source_is_rejected(self):
        r = self.write()
        self.assertEqual(r.status_code, 400, "沒有出處竟然存下去了")

    def test_rejection_is_400_not_500(self):
        """spec 056 的教訓：**正確的拒絕不該長得像故障**。"""
        r = self.write()
        self.assertEqual(r.status_code, 400)
        self.assertNotEqual(r.status_code, 500)
        self.assertTrue(r.json().get("error"), "拒絕要帶人話")

    def test_nothing_written_when_rejected(self):
        self.write()
        repo = self.repo()
        self.assertEqual(len(repo.list_why_nodes("anointed")), 0)
        repo.close()

    def test_explicit_no_basis_is_accepted(self):
        """第四種出處：明確宣告『這是我自己的判斷』——**不是逃生門，是一種終點**。"""
        r = self.write(origin="self:judgment")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "created")

    def test_url_counts_as_source(self):
        r = self.write(evidence_urls="https://example.com/paper")
        self.assertEqual(r.status_code, 200, r.text)


class TestOriginIsStoredNotDerived(WriteUnderstandingBase):
    """⚠️ 『欄位都空著』和『明確宣告沒有依據』在資料上長得一樣——所以要**存**。"""

    def test_judgment_is_distinguishable_from_missing(self):
        self.write(origin="self:judgment")
        repo = self.repo()
        rows = repo.conn.execute("SELECT origin FROM why_nodes").fetchall()
        repo.close()
        self.assertEqual([r["origin"] for r in rows], ["self:judgment"])

    def test_ai_path_keeps_empty_origin(self):
        """既有的 AI 蒸餾路徑不受影響（回歸）。"""
        r = self.c.post("/api/chat/anoint", json={"claim": "AI 來的主張"})
        self.assertEqual(r.status_code, 200)
        repo = self.repo()
        rows = repo.conn.execute("SELECT origin FROM why_nodes").fetchall()
        repo.close()
        self.assertEqual([r["origin"] for r in rows], [""])


class TestEntersCorpus(WriteUnderstandingBase):
    """⚠️ FR-005：本檔存在的主要理由。"""

    def test_hand_written_understanding_is_retrievable(self):
        self.write(claim="幾何代數比較適合處理幀間的空間變化", origin="self:judgment")
        repo = self.repo()
        bodies = [e.body for e in repo._anointed_corpus_entries()]
        repo.close()
        self.assertTrue(any("幾何代數" in b for b in bodies),
                        "自己寫的理解沒有進檢索語料——它不在你的場裡，而畫面上看不出來")

    def test_ladder_also_enters_corpus(self):
        self.write(claim="主張本體", ladder="因為 A\n因為 B", origin="self:judgment")
        repo = self.repo()
        bodies = " ".join(e.body for e in repo._anointed_corpus_entries())
        repo.close()
        self.assertIn("因為 B", bodies)


class TestSourceLinks(WriteUnderstandingBase):
    """FR-001：既有互動／既有來源當出處，要真的連上去（溯源要點得回去）。"""

    def test_conversation_as_source(self):
        repo = self.repo()
        cid = repo.save_conversation("某段互動", [{"role": "user", "content": "x"}], None)
        repo.close()
        r = self.write(conversation_id=cid)
        self.assertEqual(r.status_code, 200, r.text)
        repo = self.repo()
        row = repo.conn.execute("SELECT conversation_id, origin FROM why_nodes").fetchone()
        repo.close()
        self.assertEqual(int(row["conversation_id"]), cid)
        self.assertEqual(row["origin"], "self")

    def test_pointers_to_finds_it(self):
        """溯源：`pointers_to` 要看得到這條理解指向那段互動。"""
        repo = self.repo()
        cid = repo.save_conversation("某段互動", [{"role": "user", "content": "x"}], None)
        repo.close()
        self.write(conversation_id=cid)
        repo = self.repo()
        wid = repo.list_why_nodes("anointed")[0].id
        refs = repo.pointers_to("why_node", wid)
        repo.close()
        self.assertIn({"kind": "conversation", "ref": cid}, refs)


if __name__ == "__main__":
    unittest.main()


class TestSourceByUrl(WriteUnderstandingBase):
    """來源的身分是 **url** 不是 id——介面拿得到的是 url，路由要自己解析。"""

    def _seed_source(self, url="https://arxiv.org/abs/1234"):
        from knowfield.models import Article, Digest, DigestEntry, Item
        repo = self.repo()
        repo.save_digest(Digest(date="2026-08-26", entries=[DigestEntry(
            item=Item(source_id="s", external_id="1", title="某篇論文", url=url),
            rank=1, relevance_score=0.9, matched_topic="t",
            article=Article(item_id=0, body="內文", source_url=url, headline="某篇論文"))]))
        repo.close()
        return url

    def test_source_url_resolves_to_entry(self):
        url = self._seed_source()
        r = self.write(source_url=url)
        self.assertEqual(r.status_code, 200, r.text)
        repo = self.repo()
        wid = repo.list_why_nodes("anointed")[0].id
        refs = repo.pointers_to("why_node", wid)
        repo.close()
        self.assertIn({"kind": "source", "ref": url}, refs)

    def test_unknown_url_is_not_a_source(self):
        """⚠️ 給了一個庫裡沒有的 url ⇒ 解析不到 ⇒ **不能當成有出處**放行。"""
        r = self.write(source_url="https://not-in-the-library.example/x")
        self.assertEqual(r.status_code, 400,
                         "解析不到的來源被當成有出處了——那是把『查不到』讀成『有』")


class TestOriginReachesTheList(WriteUnderstandingBase):
    """FR-004：清單上要看得出「自己寫」——不然那個區分只活在資料庫裡。"""

    def test_roots_api_carries_origin(self):
        self.write(claim="自己寫的", origin="self:judgment")
        self.c.post("/api/chat/anoint", json={"claim": "AI 來的"})
        rows = self.c.get("/api/roots").json()["anointed"]
        by = {r["claim"]: r["origin"] for r in rows}
        self.assertEqual(by["自己寫的"], "self:judgment")
        self.assertEqual(by["AI 來的"], "")
