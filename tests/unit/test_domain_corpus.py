"""spec 079：聊天的語料吃領域。

⚠️ 這不是為專案做的功能，是**補一個一直都在的洞**：spec 048–052 讓知識歸屬到領域、
   側欄顯示「當前領域底下的東西」、新東西「生在你站的地方」——**唯獨聊天沒跟上**。
   你站在「音樂與數學結構」裡問問題，它照樣拿「Transformer 表示」的東西回答你。
"""
import unittest

from knowfield.store.repository import Repository
from tests.web_helpers import seed_digest, temp_db

NOW = "2026-08-27T00:00:00Z"


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        seed_digest(self.db)
        r = Repository(self.db)
        self.a = r.create_domain("領域甲")
        self.a1 = r.create_domain("甲的孩子", self.a)
        self.b = r.create_domain("領域乙")
        urls = [e.url for e in r.list_corpus_entries() if e.entry_id > 0]
        self.u_a, self.u_b = urls[0], urls[1]
        r.set_knowledge_domain("source", self.u_a, self.a1)   # 放在**子孫**裡
        r.set_knowledge_domain("source", self.u_b, self.b)
        # 三條理解：甲、乙、未歸屬
        self.w = {}
        for name, did in (("甲", self.a), ("乙", self.b), ("無", None)):
            wid = r.add_why_node(f"{name}的理解", [], [], False, 0, NOW)
            r.anoint_why_node(wid)
            if did:
                r.set_knowledge_domain("why_node", wid, did)
            self.w[name] = wid
        r.close()

    def repo(self):
        return Repository(self.db)


class TestScoping(Base):
    def test_none_means_the_whole_field(self):
        """⚠️ FR-001：既有呼叫點行為一個字都不變。"""
        r = self.repo()
        n = len(r.list_corpus_entries())
        r.close()
        self.assertGreaterEqual(n, 5)          # 2 來源 ＋ 3 理解（至少）

    def test_a_domain_includes_its_descendants(self):
        """來源掛在**子孫**上，站在祖先也要看得到——否則樹等於沒有用。"""
        r = self.repo()
        urls = {e.url for e in r.list_corpus_entries(domain=self.a) if e.entry_id > 0}
        r.close()
        self.assertEqual(urls, {self.u_a})

    def test_another_domain_sees_nothing_of_yours(self):
        r = self.repo()
        urls = {e.url for e in r.list_corpus_entries(domain=self.b) if e.entry_id > 0}
        r.close()
        self.assertEqual(urls, {self.u_b})

    def test_unassigned_is_excluded_when_scoped(self):
        """⚠️ FR-002：「站在這裡」＝「這裡有的東西」。
        把未歸屬的算進來，站哪裡都一樣——那就等於沒縮。"""
        r = self.repo()
        r.set_knowledge_domain("source", self.u_a, None)      # 變成未歸屬
        urls = {e.url for e in r.list_corpus_entries(domain=self.a) if e.entry_id > 0}
        self.assertEqual(urls, set())
        self.assertIn(self.u_a, {e.url for e in r.list_corpus_entries() if e.entry_id > 0})
        r.close()

    def test_anointed_understandings_are_scoped_too(self):
        """⚠️ FR-003：理解是**最重的吸引子**——縮了來源卻不縮它，等於根本沒縮。"""
        r = self.repo()
        got = {e.body for e in r.list_corpus_entries(domain=self.a) if e.entry_id < 0}
        r.close()
        self.assertEqual(got, {"甲的理解"})


class TestTheSilentFilterBug(Base):
    """⚠️ 實作時真的踩到的：`WhyNode` **沒有 `domain_id` 欄位**。

    在物件上 `getattr(r, "domain_id", None)` 永遠是 `None`
    ⇒ 拿它過濾會**濾掉全部**，而且**不會報錯**——只會讓聊天忽然沒有任何理解可用。
    """

    def test_whynode_really_has_no_domain_field(self):
        from knowfield.rootcause.extract import WhyNode
        self.assertFalse(hasattr(WhyNode(id=1, claim="x"), "domain_id"))

    def test_the_helper_goes_back_to_the_database(self):
        r = self.repo()
        keep = r.anointed_ids_in_domain(self.a)
        r.close()
        self.assertEqual(keep, {self.w["甲"]})       # 不是空集合

    def test_scan_no_getattr_domain_on_whynode(self):
        """掃描層：別再用 getattr 猜那個欄位。"""
        import inspect

        from knowfield.web import app as mod
        self.assertNotIn('getattr(r, "domain_id"', inspect.getsource(mod))


class TestIsolation(Base):
    def test_owner(self):
        other = Repository(self.db, owner=999)
        self.assertEqual(other.list_corpus_entries(domain=self.a), [])
        self.assertEqual(other.anointed_ids_in_domain(self.a), set())
        other.close()


class TestItActuallyReachesRetrieval(Base):
    """⚠️ 對抗性驗證翻出來的空隙：上面那些測試**全在打 repository**，
    而 `retrieve_corpus` 那條**傳遞路徑**一次都沒被執行過
    ——把 `domain=domain` 拿掉，9 條測試全部照樣綠。

    ⇒ 這是「[測試餵的是那一步的**產物**時，那一步本身沒有被測到]
    (history/140)」的第二次現身：這次不是產物，是**中間那一段**。
    """

    def _stub(self):
        import hashlib
        import types

        def vec(t):
            h = hashlib.sha256(t.encode()).digest()
            v = [b / 255 for b in h[:16]]
            n = sum(x * x for x in v) ** .5 or 1
            return [x / n for x in v]
        return types.SimpleNamespace(embed=vec, embed_many=lambda ts: [vec(t) for t in ts],
                                     dim=16)

    def test_retrieve_corpus_honours_the_domain(self):
        from knowfield.rag.service import retrieve_corpus
        r, emb = self.repo(), self._stub()
        whole = retrieve_corpus(r, emb, "理解", top_k=50, min_score=0.0)
        scoped = retrieve_corpus(r, emb, "理解", top_k=50, min_score=0.0, domain=self.a)
        r.close()
        self.assertGreater(len(whole), len(scoped))
        self.assertTrue(all(e.entry_id > 0 or e.body == "甲的理解" for e in scoped))

    def test_explicit_entries_still_win_over_domain(self):
        """⚠️ 兩個參數同時給時，`entries` 是**明確指定**⇒ 它贏。
        （spec 076 的換場靠的就是這個，不能被 domain 蓋掉。）"""
        from knowfield.rag.service import retrieve_corpus
        from knowfield.rag.types import CorpusEntry
        r, emb = self.repo(), self._stub()
        e = CorpusEntry(entry_id=1, title="外來", url="", body="外來的一段")
        got = retrieve_corpus(r, emb, "外來", top_k=5, min_score=0.0,
                              entries=[e], vectors={1: emb.embed("外來的一段")},
                              domain=self.b)
        r.close()
        self.assertEqual([x.body for x in got], ["外來的一段"])


class TestUiSaysItScoped(unittest.TestCase):
    """⚠️ FR-005：縮了範圍要**說出縮到哪裡**。

    只說「有縮」沒有用——你要判斷的是「它找不到」還是「這裡本來就沒有」，
    而那要知道「這裡」是哪裡。（`vision` FR-007 同一條。）
    """

    def _read(self, rel):
        import pathlib
        import re
        src = (pathlib.Path(__file__).resolve().parents[2] / "frontend/src" / rel
               ).read_text(encoding="utf-8")
        return re.sub(r"/\*[\s\S]*?\*/", "", re.sub(r"//.*$", "", src, flags=re.M))

    def test_chat_passes_the_domain(self):
        code = self._read("ChatPage.tsx")
        self.assertIn("0, did)", code)          # streamChat 的最後一個參數
        self.assertIn("useCurrentDomain", code)

    def test_chat_says_which_domain(self):
        code = self._read("ChatPage.tsx")
        self.assertIn("domainName", code)
        self.assertIn("底下的東西", code)

    def test_api_threads_domain_id(self):
        self.assertIn("domain_id: domainId", self._read("lib/api.ts"))
