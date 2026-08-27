"""spec 077：問完要留下東西——合成 ＋ 沉澱成 draft。

⚠️ 這一刀最重要的一條：**只寫 `knowledge/draft/`**，而它是**能力邊界不是政策**。
   使用者定的界線：「我們只會動 draft，代表短期記憶。至於如何處理 draft 就是專案的事了。」
   往上每一層的判斷是**那個專案的**；而 `experience.md` 也不是 append-only。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.github import draftout
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class TestOnlyDraft(unittest.TestCase):
    """⚠️ 結構性禁令——**組不出**別的路徑，不是「記得不要寫」。"""

    def test_path_is_always_under_knowledge_draft(self):
        for title in ("正常標題", "../../etc/passwd", "experience", "a/b/c", ""):
            p = draftout.draft_path("2026-08-27T00:00:00Z", title)
            self.assertTrue(p.startswith("knowledge/draft/"), p)
            self.assertNotIn("..", p)
            self.assertTrue(p.endswith(".md"))

    def test_never_a_space_in_the_filename(self):
        """⚠️ 空白會讓 `%20` 編碼與字面連結對不起來，半數指標靜默斷掉。"""
        self.assertNotIn(" ", draftout.draft_path("2026-08-27", "有 空白 的 標題"))

    def test_prefill_refuses_a_path_outside_draft(self):
        with self.assertRaises(ValueError):
            draftout.prefill_url("a/b", "main", "knowledge/experience.md", "x")

    def test_source_scan_no_other_write_target(self):
        """掃描層：整支程式只認得一個目的地。"""
        import inspect
        src = inspect.getsource(draftout)
        for forbidden in ("experience.md", "concepts/", "principles.md", "vision.md"):
            body = src.replace('"""', "@@@").split("@@@")
            code = "".join(body[i] for i in range(0, len(body), 2))   # 去掉 docstring
            self.assertNotIn(forbidden, code, forbidden)


class TestUrlBudget(unittest.TestCase):
    """⚠️ 實測：網址上限 ≈ 8,100 字元、中文 percent-encode **5.3 倍** ⇒ 約 1,000 字。"""

    def test_short_gets_a_url(self):
        u = draftout.prefill_url("timcsy/VizGPT", "main",
                                 "knowledge/draft/2026-08-27-x.md", "短短一段")
        self.assertTrue(u.startswith("https://github.com/timcsy/VizGPT/new/main?"))
        self.assertIn("knowledge%2Fdraft%2F", u)

    def test_long_returns_none_not_a_truncated_url(self):
        """⚠️ **截斷比拒絕更糟**——你會以為送出去了，而內容少了一半。"""
        u = draftout.prefill_url("a/b", "main", "knowledge/draft/x.md", "中" * 3000)
        self.assertIsNone(u)

    def test_branch_defaults_but_is_respected(self):
        u = draftout.prefill_url("a/b", "knowledge-python", "knowledge/draft/x.md", "x")
        self.assertIn("/new/knowledge-python?", u)


class TestRender(unittest.TestCase):
    def test_marks_itself_inferred_and_unanointed(self):
        """⚠️ 生成的脈絡**不能長得像你的理解**——那條線是這個專案的認識論。"""
        md = draftout.render("標題", "內文", [], "timcsy/VizGPT", "2026-08-27")
        self.assertIn("推論的", md)
        self.assertIn("未經冊封", md)

    def test_citations_are_listed(self):
        md = draftout.render("標題", "內文",
                             [{"path": "knowledge/experience.md", "seq": 3}],
                             "timcsy/VizGPT", "2026-08-27")
        self.assertIn("experience.md", md)
        self.assertIn("#3", md)


class TestRoute(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)
        r = Repository(self.db)
        self.bid = r.add_ext_base("timcsy/VizGPT")
        r.save_ext_fetch(self.bid, {"branch": "knowledge-python", "private": False,
                                    "truncated": False, "paths": [], "items": []})
        r.close()

    def test_returns_path_content_and_url(self):
        d = self.c.post(f"/api/bases/{self.bid}/draft",
                        json={"title": "一個想法", "body": "內文",
                              "cites": [{"path": "knowledge/experience.md", "seq": 1}]}).json()
        self.assertTrue(d["path"].startswith("knowledge/draft/"))
        self.assertIn("knowledge-python", d["url"])
        self.assertFalse(d["too_long"])

    def test_too_long_says_why(self):
        """⚠️ 靜默降級 ＝ 你不知道發生了什麼。"""
        d = self.c.post(f"/api/bases/{self.bid}/draft",
                        json={"title": "長的", "body": "中" * 3000}).json()
        self.assertTrue(d["too_long"])
        self.assertIsNone(d["url"])
        self.assertIn("約 1,000 字", d["why"])

    def test_empty_is_rejected(self):
        for b in ({"title": "", "body": "x"}, {"title": "x", "body": " "}):
            self.assertEqual(self.c.post(f"/api/bases/{self.bid}/draft", json=b).status_code, 400)

    def test_unknown_base(self):
        self.assertEqual(self.c.post("/api/bases/999999/draft",
                                     json={"title": "x", "body": "y"}).status_code, 404)


class TestTopKNotAGate(unittest.TestCase):
    """⚠️ **top-k，不設合成閘門**（使用者 2026-08-27 推翻我的 0.55）。

    我原本用「最高那一段 ≥ 0.55 才合成」，而實測那個分數**分不開**
    真相關（0.442）與不相關（0.441）——⇒ 那是拿一個**測不到的代理指標**
    替使用者做語意判斷，正好是這個庫記過的
    「程式只擋機械可判的；**會擋掉好答案的檢查要改成呈現**」。
    （它擋掉的「知識庫要怎麼收斂」，knowie 的知識庫是答得出來的。）
    """

    def _src(self):
        import inspect

        from knowfield.web import app as mod
        return inspect.getsource(mod)

    def test_no_synthesis_gate(self):
        src = self._src()
        self.assertNotIn("_ANSWER_MIN_TOP", src)
        self.assertNotIn("材料不夠強", src)

    def test_retrieval_floor_stays(self):
        """⚠️ 但**檢索的地板要留著**——它擋的是「義大利麵要煮幾分鐘」那種
        機械可判的離題（實測 0.198／0.263），那不是語意判斷。"""
        self.assertIn("_ASK_MIN = 0.35", self._src())

    def test_citations_carry_the_filename_into_the_synthesiser(self):
        """⚠️ 合成最容易磨掉的就是出處 ⇒ 段落要帶著檔名進去。"""
        src = self._src()
        i = src.index("passages = [")
        self.assertIn("headline=h.title.rsplit", src[i:i + 400])


class TestDraftUi(unittest.TestCase):
    def _read(self, rel):
        import pathlib
        import re
        src = (pathlib.Path(__file__).resolve().parents[2] / "frontend/src" / rel
               ).read_text(encoding="utf-8")
        return re.sub(r"/\*[\s\S]*?\*/", "", re.sub(r"//.*$", "", src, flags=re.M))

    def test_project_chat_says_what_it_can_read(self):
        """⚠️ 說不出讀得到哪幾層，「它不知道」與「那不在語料裡」就分不開。

        ⓘ 這條原本釘「合成不夠強時說為什麼」——而那道閘門被使用者推翻了
        （top-k，不設閘門），所以改釘還在的那個不變式。
        """
        code = self._read("components/AskProject.tsx")
        self.assertIn("in_corpus", code)
        self.assertIn("不在裡面", code)

    def test_too_long_shows_the_reason_not_a_broken_button(self):
        code = self._read("components/AskProject.tsx")
        self.assertIn("d.why", code)
        self.assertIn("d.url ?", code)          # 有網址才給按鈕

    def test_no_markdown_bold_in_plain_text(self):
        import re
        self.assertIsNone(re.search(r">\s*[^<]*\*\*[^<]*<", self._read("components/AskProject.tsx")))
