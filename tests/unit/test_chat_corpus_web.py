"""spec 029：問答併聊天——聊天引用收進的文章（US1）＋膜分層守純度（US2）。

離線：注入 chat_backend_for_test（stub 回答帶 [n]）＋corpus_search_for_test（回收進 hit）。
守衛靈魂＝收進內容是「證言」、絕不進 build_field_system_prompt 的地基、不自動變核心理解（原則 6）。
"""

import json
import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from knowfield.chat.field_chat import FieldChat, build_field_system_prompt
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class StubChat:
    """chat_backend 替身：reply 回固定字串（可帶 [n]）；search_query 也走 reply。"""
    def __init__(self, text="貓要吃貓糧 [1]。"):
        self.text = text

    def reply(self, messages):
        return self.text

    def stream(self, messages):
        yield self.text


def _corpus(*items):
    """items=(title, snippet, url) → corpus 來源替身（kind=corpus）。"""
    return lambda q: [SimpleNamespace(title=t, snippet=s, url=u, kind="corpus")
                      for t, s, u in items]


class TestChatCitesCorpus(unittest.TestCase):
    def test_corpus_source_cited_with_kind(self):          # US1 收進被引用、標 kind、cited-only
        app = build_app(temp_db())
        app.state.chat_backend_for_test = StubChat("貓要吃貓糧 [1]。")
        app.state.chat_search_for_test = lambda q: []       # 無 web
        app.state.corpus_search_for_test = _corpus(
            ("貓的飼養", "貓需要貓砂與貓糧", "https://a/1"),
            ("狗的文章", "狗很忠誠", "https://a/2"))
        text, numbered = app.state.chat_factory([], "貓怎麼養", False)
        self.assertEqual(len(numbered), 1)                  # 只列被引用的
        self.assertEqual(numbered[0]["n"], 1)
        self.assertEqual(numbered[0]["kind"], "corpus")     # 標「你收藏的」
        self.assertEqual(numbered[0]["url"], "https://a/1")

    def test_brainstorm_skips_corpus(self):                 # 腦力激盪不檢索收進
        app = build_app(temp_db())
        called = {"n": 0}

        def _spy(q):
            called["n"] += 1
            return []
        app.state.chat_backend_for_test = StubChat("純發想。")
        app.state.corpus_search_for_test = _spy
        app.state.chat_factory([], "隨便聊", True)          # brainstorm=True
        self.assertEqual(called["n"], 0)


class TestPurityGuard(unittest.TestCase):
    """US2：收進內容以證言出現，絕不進地基、不自動變核心理解（原則 6）。"""

    def test_corpus_not_in_field_prompt(self):             # 收進不進 build_field_system_prompt 地基
        app = build_app(temp_db())
        db = app.state.config.db_path
        secret = "SECRET_外部觀點_不該進地基"
        app.state.chat_backend_for_test = StubChat(f"你收的資料說… [1]。")
        app.state.chat_search_for_test = lambda q: []
        app.state.corpus_search_for_test = _corpus((secret, secret, "https://a/1"))
        app.state.chat_factory([], "問一下", False)         # 跑一輪、引用了收進
        repo = Repository(db)
        roots = repo.list_why_nodes("anointed")
        n_before = len(repo.list_why_nodes("anointed"))
        repo.close()
        self.assertNotIn(secret, build_field_system_prompt(roots))  # 地基不含它
        self.assertEqual(n_before, 0)                       # 不因引用而自動變核心理解

    def test_messages_layering(self):                       # 收進在證言塊、地基段不含它（單元）
        secret = "SECRET_證言層"
        fc = FieldChat(StubChat())
        src = [SimpleNamespace(title="t", snippet=secret, url="https://a/1", kind="corpus")]
        msgs = fc._messages([], "問", roots=[], sources=src, brainstorm=False, max_history=0)
        joined = "\n".join(m["content"] for m in msgs)
        self.assertIn(secret, joined)                       # 有出現（在證言塊）
        self.assertNotIn(secret, msgs[0]["content"])        # 但地基（system[0]）不含它


class TestAskRetired(unittest.TestCase):
    """US3：問答併入聊天、退場。"""

    def test_ask_redirects_to_chat(self):                   # /ask → 302 /chat
        c = TestClient(build_app(temp_db()))
        r = c.get("/ask", follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["location"], "/chat")

    def test_nav_has_no_ask(self):                          # 導覽不含「問答」入口
        r = TestClient(build_app(temp_db())).get("/chat")
        self.assertNotIn(">問答<", r.text)


class TestBestEffort(unittest.TestCase):
    """US-polish：檢索失敗／無語料 → 聊天照跑，不 500（教訓 3）。"""

    def test_corpus_failure_does_not_break_chat(self):      # 檢索拋例外→只 核心理解＋web
        app = build_app(temp_db())

        def _boom(q):
            raise RuntimeError("檢索炸了")
        app.state.chat_backend_for_test = StubChat("照樣回答。")
        app.state.chat_search_for_test = lambda q: []
        app.state.corpus_search_for_test = _boom
        text, numbered = app.state.chat_factory([], "問一下", False)
        self.assertEqual(text, "照樣回答。")               # 不崩、照回
        self.assertEqual(numbered, [])


if __name__ == "__main__":
    unittest.main()
