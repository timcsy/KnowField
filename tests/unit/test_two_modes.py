"""spec 074：互動／開發雙模式。

⚠️ 這一刀的核心是一條線：**外部知識進搜尋，不進檢索語料。**
   搜尋是「找得到」；語料是聊天時的**地基**。混為一談的話，別人的判準會
   **沒有經過冊封**就開始影響你的回答——而那正是原則 6 那道膜守的東西，
   且它壞掉**不會報錯**：回答只是慢慢變成別人的。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

MAGIC = "只存在於別人知識庫的一句話"


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)
        r = Repository(self.db)
        self.bid = r.add_ext_base("timcsy/VizGPT")
        r.save_ext_fetch(self.bid, {
            "branch": "knowledge-python", "private": False, "truncated": False,
            "paths": ["knowledge/experience.md", "knowledge/vision.md"],
            "items": [
                {"path": "knowledge/experience.md", "layer": "experience",
                 "body": f"## 教訓\n\n### {MAGIC}\n\n- 內文\n"},
                {"path": "knowledge/vision.md", "layer": "vision", "body": "# 路線圖\n"},
            ]})
        r.close()


class TestTheLine(Base):
    """⚠️ 進搜尋、不進語料——兩邊都要驗，而且要**行為層**不只掃描層。"""

    def test_external_knowledge_is_searchable(self):
        g = self.c.get(f"/api/search?q={MAGIC[:8]}").json()["groups"]
        ext = [x for x in g if x["kind"] == "ext"]
        self.assertTrue(ext, "外部知識搜不到——那就是 Spark 跟即時通訊搜不到彼此的病")
        self.assertEqual(ext[0]["items"][0]["base"], "VizGPT")     # ⚠️ 一定看得出是誰的
        self.assertEqual(ext[0]["items"][0]["base_id"], self.bid)  # 點得過去

    def test_external_knowledge_is_NOT_in_the_retrieval_corpus(self):
        """⚠️ 這一條壞掉不會報錯：回答只是慢慢變成別人的。"""
        r = Repository(self.db)
        blob = " ".join((e.body or "") + (e.headline or "") + (e.title or "")
                        for e in r.list_corpus_entries())
        r.close()
        self.assertNotIn(MAGIC, blob)

    def test_search_puts_your_own_field_first(self):
        r = Repository(self.db)
        w = r.add_why_node(f"我自己寫的{MAGIC}", [], [], False, 0, "2026-08-27T00:00:00Z")
        r.anoint_why_node(w); r.close()
        kinds = [x["kind"] for x in self.c.get(f"/api/search?q={MAGIC[:8]}").json()["groups"]]
        self.assertLess(kinds.index("why_node"), kinds.index("ext"))

    def test_corpus_scan_no_ext_tables(self):
        """掃描層：語料的組成裡不該出現任何 `ext_` 表。"""
        import inspect

        from knowfield.store.repository import Repository as R
        src = inspect.getsource(R.list_corpus_entries) + inspect.getsource(
            R._anointed_corpus_entries)
        self.assertNotIn("ext_", src)


class TestDevModeReads(Base):
    def test_layer_listing_and_document(self):
        items = self.c.get(f"/api/bases/{self.bid}/layer/experience").json()["items"]
        self.assertEqual([i["path"] for i in items], ["knowledge/experience.md"])
        d = self.c.get(f"/api/ext/{items[0]['id']}").json()
        self.assertIn(MAGIC, d["body"])
        self.assertEqual(d["repo"], "timcsy/VizGPT")

    def test_unknown_document_404s(self):
        self.assertEqual(self.c.get("/api/ext/999999").status_code, 404)

    def test_isolation(self):
        other = Repository(self.db, owner=999)
        self.assertEqual(other.ext_layer_items(self.bid, "experience"), [])
        self.assertEqual(other.ext_item(1), {})
        self.assertEqual(other.search(MAGIC[:8]), [])
        other.close()


class TestUiInvariants(unittest.TestCase):
    """⚠️ 三條寫在介面結構裡的禁令。"""

    def _read(self, rel):
        import pathlib
        import re
        src = (pathlib.Path(__file__).resolve().parents[2] / "frontend/src" / rel
               ).read_text(encoding="utf-8")
        return re.sub(r"/\*[\s\S]*?\*/", "", re.sub(r"//.*$", "", src, flags=re.M))

    def test_no_move_between_modes(self):
        """⚠️ FR-007：**寫在哪就算哪邊** ⇒ 沒有「移動」這個動作。

        有了它就會有「我到底搬過去了沒」那種狀態——雙模式介面第三個坑。
        """
        code = self._read("pages/DevPage.tsx") + self._read("components/ModeSwitch.tsx")
        for forbidden in ("搬到", "移動到", "moveTo", "移到個人場"):
            self.assertNotIn(forbidden, code)

    def test_dev_mode_is_read_only(self):
        code = self._read("pages/DevPage.tsx")
        for forbidden in ("whynodeAnoint", "importBorrowed", "anoint", "method: \"POST\""):
            self.assertNotIn(forbidden, code)

    def test_persona_switcher_hidden_in_dev(self):
        """⚠️ FR-006：專案 base 天然隔離，再疊一層可見性只是負擔。

        ⓘ 這條原本釘一個**字面字串**（`{!dev && <PersonaSwitcher />}`），換個寫法就假紅。
        改成釘**不變式**：開發側欄裡沒有它，而互動側欄裡的它在 `dev ?` 的 else 那一支。
        """
        self.assertNotIn("PersonaSwitcher", self._read("components/DevSidebar.tsx"))
        code = self._read("components/ConversationSidebar.tsx")
        self.assertLess(code.index("dev ? <DevSidebar"), code.index("<PersonaSwitcher"))

    def test_dev_sidebar_is_projects_only(self):
        """⚠️ 使用者：「我的側邊欄要放的是專案，然後主要區域的左邊是檔案樹」。

        ⓘ 我先做錯過一次：把**檔案樹也塞進側欄**，於是主區只剩預覽。
        正確的是 IDE 的三段——最左專案、中間檔案樹、右邊預覽。
        而互動那套（領域／對話歷史／身分）一個都不進來。
        """
        code = self._read("components/DevSidebar.tsx")
        for forbidden in ("DomainNav", "ConvMenu", "新互動", "PersonaSwitcher", "resume="):
            self.assertNotIn(forbidden, code)
        self.assertIn("pages.bases", code)              # 它列的是**專案**
        self.assertNotIn("pages.baseLayer", code)       # ⚠️ 檔案樹不在側欄
        self.assertNotIn("Markdown", code)              # 預覽也不在側欄

    def test_dev_page_has_tree_and_preview(self):
        """主區＝檔案樹｜預覽，而**預覽要拿到剩下的整片寬度**。"""
        code = self._read("pages/DevPage.tsx")
        self.assertIn("FileTree", code)                 # 樹在這裡
        self.assertIn("Markdown", code)                 # 預覽也在這裡
        self.assertIn("flex-1", code)                   # 預覽吃掉剩下的
        self.assertIn("min-w-0", code)                  # ⚠️ 少了它，長行會把樹擠爛
        self.assertIn('sp.get("doc")', code)            # 選取只讀 URL

    def test_tree_is_a_real_tree(self):
        """⚠️ 使用者：「這邊用檔案樹呈現會比較好」。

        之前是「層的籤 ＋ 平面清單」——那個形狀**說不出巢狀**，
        而 `knowledge/skills/knowie-pull/SKILL.md` 本來就是巢狀的。
        """
        code = self._read("components/FileTree.tsx")
        self.assertIn("children", code)                 # 有巢狀
        self.assertIn("buildTree", code)
        page = self._read("pages/DevPage.tsx")
        self.assertIn("pages.baseTree", page)           # 一次拿全部路徑才畫得出樹
        self.assertNotIn("pages.baseLayer", page)       # 不再分層拿

    def test_expansion_is_not_in_the_url(self):
        """⚠️ 展開狀態是**當下的視線**，不是位置。

        塞進網址的話，分享出去的連結會帶著你的展開狀態——那不是對方要的東西。
        （而 `?doc=` 是位置，所以它在網址裡。）
        """
        code = self._read("components/FileTree.tsx")
        self.assertNotIn("useSearchParams", code)
        self.assertIn("useState", code)

    def test_mobile_is_master_detail(self):
        """⚠️ 手機上三欄不可能 ⇒ 沒選檔＝樹滿版、選了＝預覽滿版＋「← 檔案」。

        而它**不需要新狀態**——「有沒有選檔」本來就在網址裡。
        """
        code = self._read("pages/DevPage.tsx")
        self.assertIn('iid && "hidden md:flex"', code)      # 選了檔 → 手機藏樹
        self.assertIn('!iid && "hidden md:block"', code)    # 沒選檔 → 手機藏預覽
        self.assertIn("md:hidden", code)                    # 返回鍵只在手機
        self.assertIn("← 檔案", code)

    def test_dev_route_is_full_width(self):
        self.assertIn('pathname.startsWith("/dev")', self._read("Layout.tsx"))

    def test_bases_entry_not_in_interaction_nav(self):
        """⚠️ 使用者：「不要顯示『別的知識庫』了」——它是**開發**的事。"""
        code = self._read("components/ConversationSidebar.tsx")
        self.assertNotIn("別的知識庫", code)
        self.assertIn("管理專案", self._read("components/DevSidebar.tsx"))

    def test_switching_mode_does_not_close_the_mobile_drawer(self):
        """⚠️ 使用者：「行動版切換到開發的時候，側邊欄會自己縮回去」。

        原因：`ModeSwitch` 拿到 `onNavigate` 就在點擊時關抽屜。
        而「選了一個目的地」才該關它——**切模式正好相反**：你切過去就是
        要看新的那份側欄（開發那邊是專案清單）。關掉等於把你要看的東西收走。
        ⇒ 判準：**「導覽到某處」關抽屜；「換一組導覽」不關。**
        """
        code = self._read("components/ModeSwitch.tsx")
        self.assertNotIn("onNavigate", code)
        self.assertIn("<ModeSwitch />", self._read("components/ConversationSidebar.tsx"))

    def test_mode_switch_reachable_without_opening_the_drawer(self):
        """手機頂端那條也要有——不然切模式要先點漢堡。"""
        self.assertIn("<ModeSwitch />", self._read("Layout.tsx"))

    def test_tree_text_is_not_tiny(self):
        """⚠️ 使用者：「樹的字有點小」。檔案樹是**要一直讀**的東西，不是註腳。"""
        code = self._read("components/FileTree.tsx")
        self.assertIn("text-sm", code)
        # 檔名那一行不該是 text-xs／更小
        self.assertNotIn("text-left text-xs", code)
        self.assertNotIn("text-[10px]", code)

    def test_mode_lives_in_the_url(self):
        """FR-002：可分享、上一頁有用、重整不掉。"""
        code = self._read("components/ModeSwitch.tsx")
        self.assertIn("useLocation", code)
        self.assertIn('"/dev"', code)
        self.assertNotIn("useState", code)      # 模式不是元件狀態

    def test_search_results_show_which_base(self):
        code = self._read("components/CommandPalette.tsx")
        self.assertIn("h.base", code)
        self.assertIn('ext:', code.replace(" ", "").replace('"ext":', "ext:"))
