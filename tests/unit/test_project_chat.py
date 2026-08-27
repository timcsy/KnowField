"""spec 076：對專案也能聊——語料是那個專案的 `knowledge/`。

⚠️ 這一刀的核心不是「聊天」，是**承認有兩個場**：
spec 074 我把問題寫成「外部知識該不該進檢索語料」，那是問錯了；
正確的是「**哪一個場**」。而它壞掉的方式是**沉默的**：
別人的判準悄悄變成你回答問題時的地基，畫面上一切正常。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.rag.service import retrieve_corpus
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

MAGIC = "只有這個專案的知識庫才答得出來的那句話"


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)
        r = Repository(self.db)
        self.bid = r.add_ext_base("timcsy/VizGPT")
        r.save_ext_fetch(self.bid, {
            "branch": "main", "private": False, "truncated": False,
            "paths": ["knowledge/experience.md", "knowledge/history/1-x.md"],
            "items": [
                {"path": "knowledge/experience.md", "layer": "experience",
                 "body": f"## 教訓\n\n### 一條判準\n\n- {MAGIC}\n"},
                # ⚠️ history **不在**四層裡——這一條是用來驗「沒進語料的要說得出來」
                {"path": "knowledge/history/1-x.md", "layer": "history",
                 "body": "## 轉移\n\n只在 history 裡的一句話\n"},
            ]})
        r.close()


class TestChunking(unittest.TestCase):
    def test_splits_on_headings_not_blindly_by_size(self):
        """⚠️ 照字數盲切會把一條判準腰斬，而腰斬過的塊檢索得到也讀不懂。"""
        md = "## 甲\n\n甲的內容\n\n### 乙\n\n乙的內容\n\n### 丙\n\n丙的內容\n"
        cs = Repository.chunk_markdown(md)
        self.assertEqual(len(cs), 3)
        self.assertTrue(cs[0].startswith("## 甲"))
        self.assertTrue(cs[1].startswith("### 乙"))

    def test_oversized_block_is_hard_split(self):
        big = "### 標題\n\n" + "\n".join(f"第 {i} 行的內容" for i in range(400))
        cs = Repository.chunk_markdown(big, size=500)
        self.assertGreater(len(cs), 1)
        self.assertTrue(all(len(c) <= 500 for c in cs))
        self.assertEqual("".join(c.replace("\n", "") for c in cs).count("第 0 行的內容"), 1)

    def test_empty(self):
        self.assertEqual(Repository.chunk_markdown(""), [])


class TestTwoFields(Base):
    """⚠️ 兩個場不互相污染——行為層與掃描層各一條（沿用 spec 074 的做法）。"""

    def test_only_the_four_layers_enter_the_project_corpus(self):
        r = self.repo() if hasattr(self, "repo") else Repository(self.db)
        n = r.sync_ext_chunks(self.bid)
        layers = r.ext_layers_in_corpus(self.bid)
        r.close()
        self.assertGreater(n, 0)
        self.assertEqual(set(layers), {"experience"})     # history 沒進
        self.assertNotIn("history", layers)

    def test_which_layers_are_in_the_corpus_is_reported(self):
        """⚠️ FR-003：說不出哪幾層進了，「答不出來」就會被讀成「它不知道」。"""
        Repository(self.db).sync_ext_chunks(self.bid)
        d = self.c.get(f"/api/bases/{self.bid}/corpus").json()
        self.assertIn("experience", d["layers"])
        self.assertEqual(d["in_corpus"], list(Repository.CHAT_LAYERS))
        self.assertNotIn("history", d["in_corpus"])

    def test_project_knowledge_is_not_in_your_own_corpus(self):
        """⚠️ spec 074 那條線不准鬆——行為層。"""
        r = Repository(self.db)
        r.sync_ext_chunks(self.bid)
        blob = " ".join((e.body or "") + (e.title or "") for e in r.list_corpus_entries())
        r.close()
        self.assertNotIn(MAGIC, blob)

    def test_scan_your_corpus_has_no_ext_tables(self):
        """掃描層。"""
        import inspect
        src = (inspect.getsource(Repository.list_corpus_entries)
               + inspect.getsource(Repository._anointed_corpus_entries))
        self.assertNotIn("ext_", src)


class TestInjectionDoesNotChangeExistingBehaviour(unittest.TestCase):
    """⚠️ `entries=`／`vectors=` 是**新的可選參數**——既有兩個呼叫點的行為一個字都不能變。"""

    def test_defaults_still_use_the_field(self):
        import inspect
        src = inspect.getsource(retrieve_corpus)
        self.assertIn("entries=None", src)
        self.assertIn("vectors=None", src)
        self.assertIn("if entries is None:", src)

    def test_vectors_are_not_written_into_the_shared_table(self):
        """⚠️ `entry_embeddings` 的 id 空間已被 digest_entries（正）與 why_nodes（負）佔了
        ——外部的塊擠進去就是等著碰撞。"""
        import inspect
        src = inspect.getsource(retrieve_corpus)
        # ⓘ 原本寫成比較兩個字串的位置，結果抓到的是 **docstring** 裡那個字
        #    ——釘一整個運算式才騙不了。
        self.assertIn("vectors if vectors is not None else repo.ensure_embeddings", src)


class TestAsk(Base):
    def _stub(self):
        # 離線 embedder：同一段文字給同一個向量，足夠驗「撈得到哪一塊」
        import hashlib
        import types

        def vec(t):
            h = hashlib.sha256(t.encode()).digest()
            v = [b / 255 for b in h[:16]]
            n = sum(x * x for x in v) ** .5 or 1
            return [x / n for x in v]
        return types.SimpleNamespace(
            embed=vec, embed_many=lambda ts: [vec(t) for t in ts],
            dim=16, __class__=type("Stub", (), {}))

    def test_ask_returns_chunks_with_their_file(self):
        """⚠️ 引用一定帶**檔案**：看不出哪一份，就沒辦法回去看原文。"""
        r = Repository(self.db)
        r.sync_ext_chunks(self.bid)
        emb = self._stub()
        miss = r.ext_chunks_missing_vectors(self.bid, "stub")
        r.save_ext_chunk_vectors([(m["id"], emb.embed(m["text"])) for m in miss], "stub")
        entries, vecs = r.ext_corpus(self.bid, "stub")
        hits = retrieve_corpus(r, emb, MAGIC, top_k=3, min_score=0.0,
                               entries=entries, vectors=vecs)
        r.close()
        self.assertTrue(hits)
        self.assertTrue(hits[0].title.startswith("knowledge/experience.md#"))

    def test_empty_question_is_rejected(self):
        self.assertEqual(self.c.post(f"/api/bases/{self.bid}/ask",
                                     json={"q": "  "}).status_code, 400)

    def test_unknown_base_404s(self):
        self.assertEqual(self.c.post("/api/bases/999999/ask",
                                     json={"q": "x"}).status_code, 404)


class TestIsolation(Base):
    def test_another_owner_sees_no_chunks(self):
        Repository(self.db).sync_ext_chunks(self.bid)
        other = Repository(self.db, owner=999)
        self.assertEqual(other.ext_layers_in_corpus(self.bid), {})
        self.assertEqual(other.ext_corpus(self.bid, "stub"), ([], {}))
        self.assertEqual(other.sync_ext_chunks(self.bid), 0)
        other.close()

    def test_removing_a_base_clears_its_chunks(self):
        r = Repository(self.db)
        r.sync_ext_chunks(self.bid)
        r.delete_ext_base(self.bid)
        n = r.conn.execute("SELECT COUNT(*) AS n FROM ext_chunks").fetchone()["n"]
        r.close()
        self.assertEqual(n, 0)


class TestAskUiSaysWhatItCanRead(unittest.TestCase):
    """⚠️ FR-003 的前端那半：**說不出哪幾層進了語料，「沒有」就會被讀成「它不知道」**。"""

    def _read(self, rel):
        import pathlib
        import re
        src = (pathlib.Path(__file__).resolve().parents[2] / "frontend/src" / rel
               ).read_text(encoding="utf-8")
        return re.sub(r"/\*[\s\S]*?\*/", "", re.sub(r"//.*$", "", src, flags=re.M))

    def test_says_which_layers_are_readable(self):
        code = self._read("components/AskProject.tsx")
        self.assertIn("in_corpus", code)
        self.assertIn("不在裡面", code)          # 明講哪幾層讀不到

    def test_distinguishes_no_result_from_no_index(self):
        """⚠️ 「還沒建索引」和「沒有相關的」是**兩件事**——長得一樣就會被誤診。"""
        code = self._read("components/AskProject.tsx")
        self.assertIn("indexing", code)
        self.assertIn("沒有相關的段落", code)
        self.assertIn("還沒建立索引", code)

    def test_no_markdown_bold_in_plain_text(self):
        import re
        self.assertIsNone(re.search(r">\s*[^<]*\*\*[^<]*<", self._read("components/AskProject.tsx")))

    def test_asking_lives_in_dev_mode_only(self):
        """⚠️ 互動模式那一頁不該有它——那會讓兩個場的界線在畫面上消失。"""
        self.assertIn("AskProject", self._read("pages/DevPage.tsx"))
        self.assertNotIn("AskProject", self._read("ChatPage.tsx"))
