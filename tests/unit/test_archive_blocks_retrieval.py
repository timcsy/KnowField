"""spec 064：封存要**真的**擋住檢索——不是只擋住畫面。

⚠️ FR-003：這裡驗的是**封存**（內容還在）而不是抹除。
抹除會把內容清空，所以就算沒濾掉，檢索也撈不到東西——測試會綠，洞還在。
**用「還有內容的遺骸」當測資，才驗得到過濾本身。**
"""
import unittest
from datetime import datetime, timezone

from knowfield.models import Article, Digest, DigestEntry, Item
from knowfield.store.repository import Repository
from tests.web_helpers import temp_db

_URL = "https://news.example/retired-pipeline-article"
_NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TestArchiveBlocksRetrieval(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.repo = Repository(self.db)
        self.repo.save_digest(Digest(date="2026-07-25", entries=[DigestEntry(
            item=Item(source_id="s", external_id="1", title="退役管線留下的新聞", url=_URL),
            rank=1, relevance_score=0.9, matched_topic="t",
            article=Article(item_id=0, body="這段內容不該再影響任何回答",
                            source_url=_URL, headline="退役管線留下的新聞"))]))

    def tearDown(self):
        self.repo.close()

    def _bodies(self):
        return [e.body for e in self.repo.list_corpus_entries()]

    def test_it_is_in_the_corpus_to_begin_with(self):
        """先確認分母——不然下面兩條可能只是在驗一個空語料。"""
        self.assertTrue(any("不該再影響" in b for b in self._bodies()))

    def test_archived_source_leaves_the_corpus(self):
        """⚠️ 只封存、**不抹除**：內容還在，所以撈不到只能是因為**真的被濾掉**。"""
        self.repo.archive_knowledge("source", _URL, _NOW)
        self.assertFalse(any("不該再影響" in b for b in self._bodies()),
                         "封存過的來源還在語料裡——它仍在影響每一個回答，而畫面上毫無跡象")

    def test_erased_source_leaves_the_corpus(self):
        self.repo.archive_knowledge("source", _URL, _NOW)
        self.repo.erase_knowledge("source", _URL, _NOW)
        self.assertEqual([e for e in self.repo.list_corpus_entries() if e.url == _URL], [])

    def test_live_source_stays(self):
        """反面：沒被封存的不能被誤殺。"""
        self.assertTrue(any(e.url == _URL for e in self.repo.list_corpus_entries()))


class TestSeedsAlsoFilterErased(unittest.TestCase):
    """FR-002：`list_seeds` 原本只濾 archived，沒濾 erased。"""

    def setUp(self):
        from knowfield.config import SEEDS_DATE
        self.db = temp_db()
        self.repo = Repository(self.db)
        self.url = "https://seed.example/paper"
        self.repo.save_digest(Digest(date=SEEDS_DATE, entries=[DigestEntry(
            item=Item(source_id="s", external_id="1", title="種子", url=self.url),
            rank=1, relevance_score=0.9, matched_topic="t",
            article=Article(item_id=0, body="種子內容", source_url=self.url, headline="種子"))]))

    def tearDown(self):
        self.repo.close()

    def test_erased_seed_is_not_a_seed(self):
        self.assertTrue(self.repo.list_seeds())
        self.repo.archive_knowledge("source", self.url, _NOW)
        self.repo.erase_knowledge("source", self.url, _NOW)
        self.assertEqual(self.repo.list_seeds(), [])


class TestUnderstandingSideUnchanged(unittest.TestCase):
    """回歸：理解那半本來就對，別改壞。"""

    def test_anointed_still_filtered(self):
        repo = Repository(temp_db())
        wid = repo.add_why_node("一條會被封存的理解", [], [], False, 0, _NOW)
        repo.anoint_why_node(wid)
        self.assertTrue(repo._anointed_corpus_entries())
        repo.archive_knowledge("why_node", wid, _NOW)
        self.assertEqual(repo._anointed_corpus_entries(), [])
        repo.close()


if __name__ == "__main__":
    unittest.main()
