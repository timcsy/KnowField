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

    def test_says_when_there_is_no_index_yet(self):
        """⚠️ 「還沒建索引」要說得出來——它跟「問了但它不知道」是**兩件事**，
        長得一樣就會被誤診。

        ⓘ 原本這條還釘「沒有相關的段落」那句文案，而 spec 078 把單輪的
        `ask` 換成了真正的聊天 ⇒ 那句話現在是**回答自己**的事（top-k、不設閘門）。
        """
        code = self._read("components/AskProject.tsx")
        self.assertIn("還沒建索引", code)
        self.assertIn("自動建", code)

    def test_no_markdown_bold_in_plain_text(self):
        import re
        self.assertIsNone(re.search(r">\s*[^<]*\*\*[^<]*<", self._read("components/AskProject.tsx")))

    def test_asking_lives_in_dev_mode_only(self):
        """⚠️ 互動模式那一頁不該有它——那會讓兩個場的界線在畫面上消失。"""
        self.assertIn("AskProject", self._read("pages/DevPage.tsx"))
        self.assertNotIn("AskProject", self._read("ChatPage.tsx"))


class TestProjectChatIsTheSameChat(unittest.TestCase):
    """spec 078：開發模式用的是**同一條聊天**（多輪、串流），只是換了場。

    ⚠️ 另做一套的話，多輪一定先壞——你問「那第二點呢？」它不記得。
    """

    def _src(self):
        import inspect

        from knowfield.web import app as mod
        return inspect.getsource(mod)

    def test_stream_takes_a_project(self):
        src = self._src()
        self.assertIn("def _stream_gen(hist, message, bare, article_id=0, source_url=\"\","
                      " ext_base_id=0)", src)
        self.assertIn('int(body.get("ext_base_id") or 0)', src)

    def test_project_mode_does_not_web_search(self):
        """⚠️ 你問的是**那個專案自己**怎麼想，網路上的東西會把它的聲音蓋掉。"""
        src = self._src()
        i = src.index("if ext_base_id:\n                    # ⚠️ 站在某個專案裡時**不撒網**")
        self.assertIn("web, sources = [], _chat_corpus(message, ext_base_id)", src[i:i + 400])

    def test_project_mode_does_not_inject_your_own_roots(self):
        """⚠️ 你自己的理解墊進去 ⇒ 你會分不清哪一句是它說的、哪一句是你本來就相信的。"""
        self.assertIn("if bare or ext_base_id:\n            roots = []", self._src())

    def test_corpus_swap_is_a_parameter_not_a_second_implementation(self):
        src = self._src()
        self.assertIn("def _chat_corpus(query, ext_base_id=0)", src)


class TestOneShapeNotTwo(unittest.TestCase):
    """⚠️ `history/112`：「**兩套介面是我自己造的**」。

    使用者要開發模式「跟互動那邊幾乎一樣」——而做第二套的話，
    兩邊會從第一天開始漂。⇒ 會漂的東西（訊息的樣子、輸入框）收成一份。
    """

    def _read(self, rel):
        import pathlib
        import re
        src = (pathlib.Path(__file__).resolve().parents[2] / "frontend/src" / rel
               ).read_text(encoding="utf-8")
        return re.sub(r"/\*[\s\S]*?\*/", "", re.sub(r"//.*$", "", src, flags=re.M))

    def test_both_use_the_shared_shape(self):
        for f in ("ChatPage.tsx", "components/AskProject.tsx"):
            code = self._read(f)
            self.assertIn("ChatShape", code, f)
            self.assertIn("UserBubble", code, f)
            self.assertIn("AssistantFlow", code, f)

    def test_the_bubble_markup_exists_in_exactly_one_place(self):
        """⚠️ 泡泡的樣式只能寫一次——寫兩次就會漂。"""
        marker = "rounded-2xl rounded-br-sm bg-muted"
        hits = [f for f in ("ChatPage.tsx", "components/AskProject.tsx",
                            "components/ChatShape.tsx") if marker in self._read(f)]
        self.assertEqual(hits, ["components/ChatShape.tsx"])

    def test_project_chat_uses_the_same_stream(self):
        """⚠️ 另做一套後端 ⇒ 多輪先壞（「那第二點呢？」它不記得）。"""
        code = self._read("components/AskProject.tsx")
        self.assertIn("streamChat", code)
        self.assertNotIn("baseAsk", code)      # 不用那支單輪的


class TestProjectPromptDoesNotLieAboutYou(unittest.TestCase):
    """⚠️ 站在專案裡時 `roots` 是空的——**那是我們刻意換場造成的空缺**。

    第一次實跑它說「你目前**還沒有存下自己的理解**」。使用者有 80 條。
    ⇒ 把工程上的隔離講成關於使用者的事實，是**憑空生資訊**。
    """

    def test_project_prompt_says_where_you_are_not_what_you_lack(self):
        from knowfield.chat.field_chat import build_field_system_prompt
        p = build_field_system_prompt([], project="VizGPT")
        self.assertIn("VizGPT", p)
        self.assertIn("不要說他沒有存過理解", p)
        self.assertNotIn("知識庫還空", p)

    def test_empty_field_without_a_project_still_says_so(self):
        """⚠️ 而**沒站在專案裡**時，空的場仍然要老實講——那時它是真的。"""
        from knowfield.chat.field_chat import build_field_system_prompt
        p = build_field_system_prompt([])
        self.assertIn("還空", p)

    def test_sources_are_labelled_as_the_projects_not_yours(self):
        """⚠️ 「你收藏的」會讓那個專案的判準聽起來像你的東西。"""
        import inspect

        from knowfield.chat import field_chat
        src = inspect.getsource(field_chat)
        self.assertIn('("這個專案的知識庫" if project else "你收藏的")', src)
        self.assertIn("不是使用者的地基", src)
