"""spec 074／080：互動／開發雙模式。

⚠️ 這一刀原本的核心是「**外部知識進搜尋、不進檢索語料**」。
   spec 080 把它換掉了：專案的知識檔**就是來源**（外部證言那一層），
   ⇒ 它進語料，但**帶著出處**、而且**軟於你冊封過的理解**——
   原則 6 那道膜守的不是「不准進來」，是「**分得出是誰說的**」。
   ⚠️ 而**沒落成來源的快照**（`ext_items`）**仍然不准進語料**：
   那才是無主的、看不出出處的那一份，而它壞掉不會報錯。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

MAGIC = "只存在於別人知識庫的一句話"
#: ⚠️ 只出現在**來源**、不在快照裡——預覽讀錯邊就會紅
ONLY_SOURCE = "這一句只在落成的來源裡"


class _FakeEmb:
    """不打網路的嵌入（維度隨便，測的是落庫不是相似度）。"""
    def embed_many(self, texts):
        return [[float(len(t) % 7), 1.0, 0.0] for t in texts]

    def embed(self, text):
        return self.embed_many([text])[0]


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

    def test_the_raw_snapshot_is_NOT_in_the_retrieval_corpus(self):
        """⚠️ 只抓下來、**沒落成來源**的那一份不進語料（spec 080 之後仍然成立）。

        它沒有 url、沒有出處、也沒有進過 `_ingest_markdown` 的去重
        ——進了語料就是一段**無主的話**，而這壞掉不會報錯：回答只是慢慢變成別人的。
        """
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
    """spec 080 FR-004：⚠️ 樹讀的是**來源**，不是抓下來的快照。"""

    def _as_sources(self):
        """把這個 base 落成來源（`_base_to_sources` 的最小等價：走 ingest 的共同出口）。"""
        from knowfield.ingest.service import ContentIngestService
        r = Repository(self.db)
        svc = ContentIngestService(r, _FakeEmb(), None)
        did = r.create_domain("VizGPT")
        r.set_ext_domain(self.bid, did)
        # ⚠️ 內容**故意跟快照不一樣**（`ONLY_SOURCE`），而 `SKILL.md` **只存在於來源**
        #    ——否則「預覽讀來源」跟「預覽讀快照」長得一模一樣，攻擊改了也不會紅。
        for path, body in (("knowledge/experience.md", f"### {MAGIC}\n\n- {ONLY_SOURCE}\n"),
                           ("knowledge/skills/x/SKILL.md", f"{ONLY_SOURCE}・巢狀的一份\n")):
            url = f"github://timcsy/VizGPT/{path}"
            svc._ingest_markdown(body, path.split("/")[-1], url)
            r.set_knowledge_domain("source", url, did, by="machine")
        r.close()
        return did

    def test_tree_lists_the_sources_not_the_snapshot(self):
        did = self._as_sources()
        d = self.c.get(f"/api/bases/{self.bid}/tree").json()
        self.assertEqual([i["path"] for i in d["items"]],
                         ["knowledge/experience.md", "knowledge/skills/x/SKILL.md"])
        # ⚠️ 快照裡有 vision.md 而**來源裡沒有** ⇒ 樹上也不准有它
        self.assertNotIn("knowledge/vision.md", [i["path"] for i in d["items"]])
        self.assertEqual(d["domain_id"], did)

    def test_archived_file_leaves_the_tree(self):
        """⚠️ 讀快照的話，封存掉的檔還會留在樹上——**看得到、問不到**，而沒人會發現。"""
        self._as_sources()
        r = Repository(self.db)
        r.delete_source("github://timcsy/VizGPT/knowledge/experience.md")
        r.close()
        paths = [i["path"] for i in self.c.get(f"/api/bases/{self.bid}/tree").json()["items"]]
        self.assertEqual(paths, ["knowledge/skills/x/SKILL.md"])

    def test_preview_reads_the_source_chunks(self):
        """⚠️ 預覽跟回答要用**同一份**——不然你看到的跟它引用的不是同一段文字。"""
        self._as_sources()
        d = self.c.get(f"/api/bases/{self.bid}/file",
                       params={"path": "knowledge/experience.md"}).json()
        self.assertIn(ONLY_SOURCE, d["body"], "預覽回頭讀了快照")
        self.assertEqual(d["repo"], "timcsy/VizGPT")
        # 只存在於來源的那一份也要預覽得到（快照裡根本沒有它）
        d2 = self.c.get(f"/api/bases/{self.bid}/file",
                        params={"path": "knowledge/skills/x/SKILL.md"}).json()
        self.assertIn(ONLY_SOURCE, d2["body"])

    def test_unknown_document_404s(self):
        self._as_sources()
        self.assertEqual(self.c.get(f"/api/bases/{self.bid}/file",
                                    params={"path": "knowledge/nope.md"}).status_code, 404)
        self.assertEqual(self.c.get("/api/bases/999999/tree").status_code, 404)

    def test_isolation(self):
        self._as_sources()
        other = Repository(self.db, owner=999)
        self.assertEqual(other.project_sources("github://timcsy/VizGPT/"), [])
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

    def test_persona_is_in_both_sidebars(self):
        """⚠️ **推翻 spec 074 FR-006**（「persona 不進開發模式」）。

        當時的理由是「專案 base 天然隔離」——那在專案是**第二個場**時成立。
        spec 080 之後專案就是**來源**，跟你的東西同一個庫 ⇒ 身分當然也管得到它。
        使用者 2026-08-27：「開發模式的側邊欄要幾乎跟互動模式一樣」。
        ⇒ 釘的是**不變式**：它在雙模式分支**之上**（所以兩邊都有），不是某個字面寫法。
        """
        code = self._read("components/ConversationSidebar.tsx")
        self.assertLess(code.index("<PersonaSwitcher"), code.index("dev ? <DevSidebar"))

    def test_dev_sidebar_mirrors_the_interaction_one(self):
        """⚠️ 使用者：「開發模式的側邊欄要幾乎跟互動模式一樣」。

        ⇒ **同一個骨架**：你站在哪（導航列）→ ＋主要動作 → 這底下有什麼（帶計數）
        → 最近（時間軸）→ 範圍說明。
        ⓘ 但**檔案樹仍不在側欄**——它在主區的左半（IDE 三段：專案／檔案樹／預覽）。
        我先做錯過一次，把樹塞進側欄，於是主區只剩預覽。
        """
        code = self._read("components/DevSidebar.tsx")
        self.assertIn("pages.bases", code)              # 你站在哪：專案
        self.assertIn("＋ 新增專案", code)               # 對應「＋ 新互動」
        self.assertIn("layersOf", code)                 # 這底下有什麼（帶計數）
        self.assertIn("readRecentDocs", code)           # 時間軸（對應「最近的互動」）
        self.assertNotIn("FileTree", code)              # ⚠️ 檔案樹不在側欄
        self.assertNotIn("Markdown", code)              # 預覽也不在側欄
        self.assertNotIn("resume=", code)               # 互動的對話歷史不進來

    def test_dev_sidebar_says_whose_knowledge_this_is(self):
        """⚠️ 看不出是別人的，就等於冒充你自己的知識（原則 6 那道膜）。"""
        self.assertIn("別人專案", self._read("components/DevSidebar.tsx"))

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
        import re
        code = self._read("pages/DevPage.tsx")
        # ⓘ 原本釘 `"hidden md:block"` 這個**字面**，換成 md:flex 就假紅（今天第三次）。
        #    釘的是**不變式**：兩塊各有一條「手機上依 iid 隱藏」的規則。
        self.assertTrue(re.search(r'[^!]path && "hidden md:\w+"', code), "選了檔要在手機藏樹")
        self.assertTrue(re.search(r'!path && "hidden md:\w+"', code), "沒選檔要在手機藏預覽")
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

    def test_managing_projects_lives_inside_dev_mode(self):
        """⚠️ 使用者：「管理專案那邊也要修一下，更好融入現在的開發 UI」。

        不融入的**根本原因不是樣式**：那一頁在 `/bases`，而 `dev` 是
        `pathname.startsWith("/dev")` ⇒ 點進去側欄整個切回互動那套。
        ⇒ 判準：**「它算哪個模式」是路由的事，不是樣式的事。**
        """
        main = self._read("main.tsx")
        self.assertIn('path="dev/bases"', main)
        self.assertIn('path="bases"', main)          # 舊連結還要指得到
        self.assertIn("Navigate", main)
        for f in ("components/DevSidebar.tsx", "pages/DevPage.tsx"):
            self.assertNotIn('to="/bases"', self._read(f))

    def test_sidebar_knows_where_you_are(self):
        """⚠️ 用 `useLocation` 不用 `window.location`——後者不隨路由更新，
        於是「我在哪」會停在你第一次進來的那一頁。"""
        code = self._read("components/DevSidebar.tsx")
        self.assertIn("useLocation", code)
        self.assertNotIn("window.location", code)

    def test_removing_a_base_says_what_survives(self):
        """⚠️ 刪除的對話框要講**留下什麼**——不然人不敢按，或按了才後悔。"""
        code = self._read("pages/BasesPage.tsx")
        self.assertIn("baseRemove", code)
        self.assertIn("confirm(", code)
        self.assertIn("不受影響", code)          # 已冊封的借來判準
        self.assertIn("重新加回來", code)        # 它是快照，不是唯一副本

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
