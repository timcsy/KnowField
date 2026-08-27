"""spec 080：專案落成來源。

⚠️ 這一刀**退掉**我在 spec 076／078 蓋的兩個場——既有的「來源」那一層語意逐字就是對的：
   「外部證言：可以引用，但比他精選的理解軟⋯別當成他的地基」。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

FETCH = {
    "branch": "main", "private": False, "truncated": False,
    "paths": ["knowledge/experience.md", "knowledge/history/1-x.md"],
    "items": [
        {"path": "knowledge/experience.md", "layer": "experience",
         "body": "## 教訓\n\n### 一條判準\n\n- 內文夠長才切得出塊，這裡多寫幾個字。\n"},
        {"path": "knowledge/history/1-x.md", "layer": "history",
         "body": "## 轉移\n\n舊的改成新的，因為某個假設被推翻了。\n"},
    ],
}


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)

    def repo(self):
        return Repository(self.db)


class TestStaleSources(Base):
    """⚠️ FR-003 的另一半：**repo 裡刪掉的檔案**。

    不處理的話那些來源會永遠留著、而且**還在語料裡**——你以為場反映那個專案
    現在的樣子，其實混著幾個月前刪掉的東西，而且不會報錯。
    """

    def _seed(self, urls):
        """⚠️ 走 `ingest_seed`（種子容器）——**收進來的東西都在那裡**，
        而 `delete_source` 的封存也只作用在那個容器上。
        用一般 digest 建資料的話，封存會靜默地什麼都不做（回 0）。"""
        from knowfield.models import Article, Item
        r = self.repo()
        for i, u in enumerate(urls):
            r.ingest_seed(Item(source_id="content", external_id=f"{u}#1", title=f"t{i}", url=u),
                          Article(item_id=0, body="內容", source_url=u, headline=f"h{i}"))
        return r

    def test_finds_what_is_gone(self):
        p = "github://a/b/"
        r = self._seed([p + "knowledge/x.md", p + "knowledge/y.md", "https://other/1"])
        gone = r.stale_project_sources(p, {p + "knowledge/x.md"})
        r.close()
        self.assertEqual(gone, [p + "knowledge/y.md"])

    def test_does_not_touch_other_projects_or_web_sources(self):
        """⚠️ 前綴比對錯了就會把別的專案（或你收的網頁）一起清掉。"""
        r = self._seed(["github://a/b/k.md", "github://a/bb/k.md", "https://x/1"])
        gone = r.stale_project_sources("github://a/b/", set())
        r.close()
        self.assertEqual(gone, ["github://a/b/k.md"])

    def test_archived_ones_are_not_reported_again(self):
        p = "github://a/b/"
        r = self._seed([p + "k.md"])
        r.delete_source(p + "k.md")
        gone = r.stale_project_sources(p, set())
        r.close()
        self.assertEqual(gone, [])          # 已經是遺骸了，不用再封一次

    def test_isolation(self):
        p = "github://a/b/"
        self._seed([p + "k.md"]).close()
        other = Repository(self.db, owner=999)
        self.assertEqual(other.stale_project_sources(p, set()), [])
        other.close()


class TestFetchCreatesSources(Base):
    """抓取 → 來源，而且**歸屬跟抓取同時發生**。

    ⚠️ 這一組原本全是**掃原始碼**，而三種攻擊（只在新收時歸屬／前綴放寬／不走共同出口）
    **一種都沒撞紅**——掃描器看得到「有沒有寫那個字」，看不到「它做了什麼」。
    ⇒ 改成真的跑一次抓取（GitHub 那層樁掉）。
    """

    def _run_fetch(self, items=None, repo_full="timcsy/Demo"):
        """把 GitHub 那層樁掉，跑真正的落庫路徑。"""
        import types

        from knowfield.web import app as mod
        fetched = {**FETCH, "items": items if items is not None else FETCH["items"]}
        fetched["paths"] = [it["path"] for it in fetched["items"]]
        gh = types.SimpleNamespace(fetch=lambda repo, workers=8: fetched,
                                   repos=lambda: [], token=lambda: "t")
        self.app.state.github_for_test = gh
        r = self.repo()
        bid = r.add_ext_base(repo_full)
        r.close()
        self.c.post(f"/api/bases/{bid}/refresh")     # 背景任務在 TestClient 裡同步跑
        return bid

    def test_knowledge_files_become_sources_in_the_project_domain(self):
        self._run_fetch()
        r = self.repo()
        did = next(d["id"] for d in r.list_domains() if d["name"] == "Demo")
        urls = {e.url for e in r.list_corpus_entries(domain=did) if e.entry_id > 0}
        r.close()
        self.assertEqual(urls, {"github://timcsy/Demo/knowledge/experience.md",
                                "github://timcsy/Demo/knowledge/history/1-x.md"})

    def test_the_base_remembers_its_domain(self):
        """⚠️ **記在 base 上**，別回頭靠 repo 名去撈領域——改個名就對不上，

        而對不上時聊天只是**少了證言**（照樣回答），不會有任何錯誤訊息。
        """
        bid = self._run_fetch()
        r = self.repo()
        did = next(d["id"] for d in r.list_domains() if d["name"] == "Demo")
        row = next(b for b in r.list_ext_bases() if int(b["id"]) == bid)
        r.close()
        self.assertEqual(row["domain_id"], did)
        self.assertEqual(self.c.get(f"/api/bases/{bid}/tree").json()["domain_id"], did)

    def test_refetch_does_not_duplicate_and_keeps_the_domain(self):
        """⚠️ 第二次抓時 `status` 是 `exists` ⇒ **只在新收時歸屬的話，重抓永遠補不上**。"""
        self._run_fetch()
        r = self.repo()
        did = next(d["id"] for d in r.list_domains() if d["name"] == "Demo")
        r.set_knowledge_domain("source", "github://timcsy/Demo/knowledge/experience.md", None)
        r.close()
        self._run_fetch()                                    # 重抓
        r = self.repo()
        urls = {e.url for e in r.list_corpus_entries(domain=did) if e.entry_id > 0}
        n = len([e for e in r.list_corpus_entries() if e.entry_id > 0])
        r.close()
        self.assertIn("github://timcsy/Demo/knowledge/experience.md", urls)   # 歸屬補回來了
        self.assertLessEqual(n, 8)                                            # 沒有增生

    def test_a_deleted_file_stops_being_in_the_corpus(self):
        """⚠️ 不處理的話你以為場反映那個專案現在的樣子，其實混著幾個月前刪掉的東西。"""
        self._run_fetch()
        self._run_fetch(items=[FETCH["items"][0]])           # 第二個檔被刪了
        r = self.repo()
        urls = {e.url for e in r.list_corpus_entries() if e.entry_id > 0}
        r.close()
        self.assertNotIn("github://timcsy/Demo/knowledge/history/1-x.md", urls)
        self.assertIn("github://timcsy/Demo/knowledge/experience.md", urls)

    def test_another_project_is_untouched(self):
        """⚠️ 前綴比對放寬 ⇒ 會把別的專案一起清掉。"""
        self._run_fetch(repo_full="timcsy/Demo")
        self._run_fetch(repo_full="timcsy/DemoTwo")
        self._run_fetch(items=[], repo_full="timcsy/Demo")   # Demo 全刪
        r = self.repo()
        urls = {e.url for e in r.list_corpus_entries() if e.entry_id > 0}
        r.close()
        self.assertTrue(any(u.startswith("github://timcsy/DemoTwo/") for u in urls))
        self.assertFalse(any(u.startswith("github://timcsy/Demo/") for u in urls))

    def test_chunks_and_embeddings_come_for_free(self):
        """⚠️ 走既有的共同出口 ⇒ 切塊、嵌入、進語料全部免費；另做一條就要重寫四件事。"""
        self._run_fetch()
        r = self.repo()
        n = len([e for e in r.list_corpus_entries()
                 if e.entry_id > 0 and e.url.startswith("github://")])
        r.close()
        self.assertGreaterEqual(n, 2)          # 有塊，而且進了語料


class TestNoShadowedMethods(unittest.TestCase):
    """⚠️ 實作這一刀時撞到的：`Repository` 曾有**兩個 `delete_source`**
    （刪訂閱來源／封存收進的來源），後定義的把前面那支蓋掉，**它從那天起就到不了**。

    ⇒ 判準：**同一個類別裡出現同名方法，那不是重載，是其中一支已經死了。**
    而它不會報錯——只會在某天有人呼叫「另一個意思」時，靜默做錯事。
    """

    def test_repository_has_no_duplicate_method_names(self):
        import ast
        import inspect

        from knowfield.store import repository as mod
        tree = ast.parse(inspect.getsource(mod))
        cls = next(n for n in tree.body
                   if isinstance(n, ast.ClassDef) and n.name == "Repository")
        names = [n.name for n in cls.body if isinstance(n, (ast.FunctionDef,))]
        dup = {n for n in names if names.count(n) > 1}
        self.assertEqual(dup, set(), f"同名方法（後面那支蓋掉前面）：{dup}")

    def test_both_meanings_are_still_reachable(self):
        from knowfield.store.repository import Repository
        self.assertTrue(hasattr(Repository, "delete_feed"))     # 刪訂閱
        self.assertTrue(hasattr(Repository, "delete_source"))   # 封存收進的


class TestStatusDoesNotLie(Base):
    """⚠️ 實跑抓到的：`save_ext_fetch` 把狀態設成 `ok`，而**落成來源還沒做完**。

    我因此查得太早，看到「1 個檔、歸屬 0 筆」以為功能壞了——其實只是還在跑。
    ⇒ 「工具回報成功 ≠ 它做到了」。狀態要**在全部做完之後**才變 ok。
    """

    def test_ok_comes_after_the_sources_are_in(self):
        import inspect

        from knowfield.web import app as mod
        src = inspect.getsource(mod)
        i = src.index("def _fetch_base")
        body = src[i:i + 1600]
        self.assertLess(body.index("_base_to_sources"), body.index('set_ext_status(bid, "ok")'))
        self.assertIn('set_ext_status(bid, "indexing")', body)


class TestThereIsOnlyOneField(Base):
    """spec 080 FR-005：⚠️ **「站在專案裡」不再是第二個場**。

    在此之前聊天有兩條語料分支（`ext_chunks` 換場、另一套門檻 0.35）。
    兩套語料一定會漂，而**漂掉的那一套不會報錯**——它只是慢慢答得跟另一邊不一樣。
    ⇒ 這裡守的是**結構性禁令**：那條路徑要**不存在**，不是「不要走」。
    """

    def _web_src(self):
        import inspect

        from knowfield.web import app as mod
        return inspect.getsource(mod)

    def test_no_second_corpus_path_in_chat(self):
        src = self._web_src()
        for gone in ("ext_base_id", "_ext_corpus_ready", "_ASK_MIN", "ext_corpus("):
            self.assertNotIn(gone, src, f"第二個場的殘骸還在：{gone}")

    def test_nothing_writes_ext_chunks_any_more(self):
        """⚠️ 表留著只為了清正式庫的舊列——**沒有任何程式再寫它**。"""
        import inspect

        from knowfield.store import repository as mod
        src = inspect.getsource(mod)
        for gone in ("sync_ext_chunks", "ext_chunks_missing_vectors", "save_ext_chunk_vectors"):
            self.assertNotIn(f"def {gone}", src, f"還有人在填 ext_chunks：{gone}")
        # 只剩 `delete_ext_base` 的清理（＋ OWNED_TABLES 的宣告）
        self.assertLessEqual(src.count("ext_chunks"), 2)

    def test_the_project_chat_is_the_same_chat(self):
        """⚠️ 另做一套的話，多輪會先壞（「那第二點呢？」它不記得），形狀也會從第一天開始漂。"""
        import pathlib
        code = (pathlib.Path(__file__).resolve().parents[2]
                / "frontend/src/components/AskProject.tsx").read_text(encoding="utf-8")
        self.assertIn("streamChat", code)           # 同一條串流
        self.assertIn("ChatShape", code)            # 同一份形狀
        self.assertNotIn("pages.baseAsk", code)     # 不是第二支問答
        self.assertNotIn("baseDraft", code)         # spec 077 已退役

    def test_scoping_names_where_you_stand(self):
        """⚠️ `roots` 被領域濾空之後，模型會講成「你還沒存下自己的理解」——

        而那是**我們縮出來的空缺**，不是關於他的事實（他有 80 條）。實際發生過。
        ⚠️ 而這對**每一個窄領域**都成立，不只專案 ⇒ 它必須掛在 `domain` 上。
        """
        src = self._web_src()
        i = src.index("_project = \"\"")
        self.assertIn("if domain is not None:", src[i:i + 200])


class TestOldBasesSayWhy(Base):
    """⚠️ **我這一刀留下的遷移缺口**：樹改讀來源，而 spec 080 之前抓的 base

    只有快照、沒有來源 ⇒ 樹是空的。而畫面上說「這個專案還沒有知識檔」——
    那是**假話**：187 份檔就在資料庫裡，只是樹讀的是另一份。
    ⇒ 判準：**換一份資料當讀取來源時，舊資料不會自己搬過去；
       而「空的」與「還沒搬」長得一模一樣 ⇒ 一定要分得出來。**
    """

    def test_tree_reports_the_snapshot_count(self):
        """有快照、沒來源 ⇒ 樹空的，但 `n_snapshot` 說得出檔在。"""
        r = self.repo()
        bid = r.add_ext_base("timcsy/Old")
        r.save_ext_fetch(bid, {
            "branch": "main", "private": False, "truncated": False,
            "paths": ["knowledge/experience.md"],
            "items": [{"path": "knowledge/experience.md", "layer": "experience",
                       "body": "# 舊的\n"}]})
        r.close()
        d = self.c.get(f"/api/bases/{bid}/tree").json()
        self.assertEqual(d["items"], [])
        self.assertEqual(d["n_snapshot"], 1, "說不出檔在，就等於謊稱這個專案是空的")
        self.assertEqual(d["domain_id"], 0)

    def test_ui_distinguishes_empty_from_unmigrated(self):
        import pathlib
        code = (pathlib.Path(__file__).resolve().parents[2]
                / "frontend/src/pages/DevPage.tsx").read_text(encoding="utf-8")
        self.assertIn("n_snapshot", code)
        self.assertIn("還沒落成來源", code)
        self.assertIn("pages.baseRefresh", code)   # 修的方法要就在原地
