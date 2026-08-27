"""spec 072：場自己去 GitHub 拿別的專案的 `knowledge/`。

⚠️ 這一刀最容易安靜壞掉的四處：
1. **branch 寫死 `main`** —— 實測 VizGPT 的預設分支是 `knowledge-python`，寫死會抓錯或 404。
2. **樹被截斷卻不說** —— 死指標報告就變成一份看起來很權威的漏報。
3. **owner／persona 沒帶到** —— 別人的知識混進你的場，而畫面一切正常。
4. **抓了 `knowledge/**` 以外的內容** —— 「場從來沒有拿過你的程式碼」那句話就不成立了。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.github import layer_of
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

FETCH = {
    "branch": "knowledge-python", "private": True, "truncated": False,
    "paths": ["README.md", "src/app/main.py", "knowledge/experience.md",
              "knowledge/history/001-x.md"],
    "items": [
        {"path": "knowledge/experience.md", "layer": "experience",
         "body": "### 一條判準\n\n- **來源**：`src/app/main.py`；`src/gone/dead.py`\n"},
        {"path": "knowledge/history/001-x.md", "layer": "history",
         "body": "指著 `src/app/main.py` 還在，`docs/removed.md` 不在\n"},
    ],
}


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)

    def repo(self):
        return Repository(self.db)

    def seed(self, fetched=None):
        r = self.repo()
        bid = r.add_ext_base("timcsy/VizGPT")
        r.save_ext_fetch(bid, fetched or FETCH)
        r.close()
        return bid


class TestLayer(unittest.TestCase):
    """六層由**路徑**導出，不猜。"""

    def test_all_six_layers_plus_other(self):
        for path, want in [
            ("knowledge/experience.md", "experience"), ("knowledge/vision.md", "vision"),
            ("knowledge/principles.md", "principles"), ("knowledge/concepts/a.md", "concepts"),
            ("knowledge/history/1-x.md", "history"), ("knowledge/episodes/e.md", "episodes"),
            ("knowledge/draft/d.md", "draft"), ("knowledge/skills/s/SKILL.md", "skills"),
            ("knowledge/README.md", "other"), ("knowledge/.knowie.json", "other"),
        ]:
            self.assertEqual(layer_of(path), want, path)


class TestFetchLands(Base):
    def test_counts_and_branch(self):
        """⚠️ branch 存的是抓的時候**實際**用的那個，不是 `main`。"""
        self.seed()
        b = self.c.get("/api/bases").json()["bases"][0]
        self.assertEqual(b["repo"], "timcsy/VizGPT")
        self.assertEqual(b["branch"], "knowledge-python")
        self.assertEqual(b["n_paths"], 4)          # 整棵樹，不只 knowledge/
        self.assertEqual(b["layers"], {"experience": 1, "history": 1})
        self.assertEqual(b["status"], "ok")

    def test_tree_paths_have_no_body(self):
        """⚠️ 樹是**查證用的事實**：只存路徑。程式碼的內容一個位元組都不該落庫。"""
        r = self.repo()
        bid = r.add_ext_base("timcsy/VizGPT"); r.save_ext_fetch(bid, FETCH)
        cols = [d[0] for d in r.conn.execute("SELECT * FROM ext_paths").description]
        bodies = [x["body"] for x in r.conn.execute("SELECT body FROM ext_items").fetchall()]
        r.close()
        self.assertNotIn("body", cols)
        self.assertNotIn("src/app/main.py", " ".join(bodies).replace("`", " ").split()[0:0] or [""])
        for b in bodies:                            # 只有 knowledge/ 的內容進來
            self.assertNotIn("def main", b)

    def test_refetch_replaces_not_accumulates(self):
        """重抓＝重新對齊。累積的話，刪掉的檔案會永遠留在樹裡 ⇒ 死指標永遠報不出來。"""
        bid = self.seed()
        r = self.repo()
        r.save_ext_fetch(bid, {**FETCH, "paths": ["README.md"], "items": []})
        r.close()
        b = self.c.get("/api/bases").json()["bases"][0]
        self.assertEqual((b["n_paths"], b["layers"]), (1, {}))

    def test_adding_same_repo_twice_is_one_base(self):
        r = self.repo()
        a, b = r.add_ext_base("timcsy/X"), r.add_ext_base("timcsy/X")
        r.close()
        self.assertEqual(a, b)


class TestDeadRefs(Base):
    """這一刀的**產出**——不是水管。"""

    def test_reports_paths_that_are_gone(self):
        bid = self.seed()
        d = self.c.get(f"/api/bases/{bid}/dead-refs").json()
        dead = {(x["file"], x["ref"]) for x in d["dead"]}
        self.assertIn(("knowledge/experience.md", "src/gone/dead.py"), dead)
        self.assertIn(("knowledge/history/001-x.md", "docs/removed.md"), dead)

    def test_does_not_report_paths_that_exist(self):
        bid = self.seed()
        refs = {x["ref"] for x in self.c.get(f"/api/bases/{bid}/dead-refs").json()["dead"]}
        self.assertNotIn("src/app/main.py", refs)

    def test_always_says_how_old_the_tree_is(self):
        """⚠️ 沒有抓取時間的死指標報告，是一份看起來很權威的過期漏報。"""
        bid = self.seed()
        d = self.c.get(f"/api/bases/{bid}/dead-refs").json()
        self.assertTrue(d["fetched_at"])
        self.assertIn("truncated", d)

    def test_truncated_tree_is_reported(self):
        """⚠️ 樹不完整時「找不到那個路徑」不代表它不在——要說出來。"""
        r = self.repo()
        bid = r.add_ext_base("timcsy/Big")
        r.save_ext_fetch(bid, {**FETCH, "truncated": True}); r.close()
        self.assertTrue(self.c.get(f"/api/bases/{bid}/dead-refs").json()["truncated"])

    def test_only_mechanical_judgements(self):
        """⚠️ 只報「路徑不存在」。有沒有來源、來源寫得好不好，是語意判斷 ⇒ 不報、不評分。"""
        r = self.repo()
        bid = r.add_ext_base("timcsy/Y")
        r.save_ext_fetch(bid, {**FETCH, "items": [
            {"path": "knowledge/experience.md", "layer": "experience",
             "body": "### 一條完全沒有來源的判準\n\n- 沒有來源那一行\n"}]})
        r.close()
        d = self.c.get(f"/api/bases/{bid}/dead-refs").json()
        self.assertEqual(d["dead"], [])
        self.assertNotIn("score", d)
        self.assertNotIn("quality", d)


class TestDeadRefsIsMechanical(Base):
    """⚠️ 實跑翻出來的：第一版把 **467 條**報成死指標，其中真的只有個位數。

    一份 90% 是雜訊的報告等於沒有報告——沒有人會讀第二次。
    而雜訊全部來自**我在猜什麼算路徑**，那是語意判斷偽裝成機械判斷。
    """

    def _dead(self, body, paths):
        r = self.repo()
        bid = r.add_ext_base("timcsy/N")
        r.save_ext_fetch(bid, {"branch": "main", "private": False, "truncated": False,
                               "paths": paths, "items": [{"path": "knowledge/experience.md",
                                                          "layer": "experience", "body": body}]})
        r.close()
        return {x["ref"] for x in self.c.get(f"/api/bases/{bid}/dead-refs").json()["dead"]}

    def test_fractions_and_field_names_are_not_paths(self):
        """`3/64` 是分數、`why_nodes.kind` 是欄位、`id/topic/title` 是欄位列表。"""
        got = self._dead("看 `3/64` 與 `63/64`，欄位 `why_nodes.kind`、`id/topic/title`",
                         ["knowledge/experience.md"])
        self.assertEqual(got, set())

    def test_partial_paths_resolve_by_suffix(self):
        """⚠️ 人會寫**部分路徑**：`store/schema.py` 指的是 `src/knowfield/store/schema.py`。

        逐字相等比對會把真的存在的檔案報成死的——那比漏報更糟，因為它會被相信。
        """
        got = self._dead("見 `store/schema.py` 與 `schema.py`",
                         ["src/knowfield/store/schema.py", "knowledge/experience.md"])
        self.assertEqual(got, set())

    def test_knowledge_relative_refs_resolve(self):
        """`history/040`（沒有副檔名）＝ `knowledge/history/040-….md` 的前綴。"""
        got = self._dead("見 `history/040` 與 `experience.md` 與 `concepts/場.md`",
                         ["knowledge/history/040-x.md", "knowledge/experience.md",
                          "knowledge/concepts/場.md"])
        self.assertEqual(got, set())

    def test_a_genuinely_deleted_file_is_still_reported(self):
        """⚠️ 收窄雜訊不能連真的一起收掉——這是實跑的已知答案。"""
        got = self._dead("來源：`digest/builder.py`", ["src/knowfield/store/schema.py"])
        self.assertEqual(got, {"digest/builder.py"})

    def test_deleted_knowledge_relative_ref_is_reported(self):
        got = self._dead("見 `draft/2026-08-10` 與 `skills/gone`",
                         ["knowledge/draft/2026-08-16-x.md"])
        self.assertEqual(got, {"draft/2026-08-10", "skills/gone"})


class TestParseRepo(Base):
    def test_accepts_url_and_shorthand(self):
        for given in ["https://github.com/timcsy/VizGPT", "https://github.com/timcsy/VizGPT.git",
                      "git@github.com:timcsy/VizGPT.git", "timcsy/VizGPT",
                      "https://github.com/timcsy/VizGPT/"]:
            r = self.c.post("/api/bases", json={"repo": given})
            self.assertEqual(r.json().get("repo"), "timcsy/VizGPT", given)

    def test_rejects_garbage(self):
        for bad in ["", "   ", "not-a-repo", "https://example.com/"]:
            self.assertEqual(self.c.post("/api/bases", json={"repo": bad}).status_code, 400, bad)


class TestIsolation(Base):
    """⚠️ 別人的知識**也**是有主人的——漏掉就是跨身分外洩，而畫面一切正常。"""

    def test_another_owner_sees_nothing(self):
        self.seed()
        other = Repository(self.db, owner=999)
        self.assertEqual(other.list_ext_bases(), [])
        self.assertEqual(other.dead_refs(1), {})
        other.close()

    def test_persona_isolation(self):
        r = self.repo(); pid = r.create_persona("分身"); r.close()
        self.c.cookies.set("kf_persona", str(pid))
        self.c.post("/api/bases", json={"repo": "timcsy/OnlyMine"})
        self.assertEqual(len(self.c.get("/api/bases").json()["bases"]), 1)
        self.c.cookies.clear()
        self.assertEqual(self.c.get("/api/bases").json()["bases"], [])


class TestNeverFetchesCode(unittest.TestCase):
    """⚠️ 這一刀的**結構性承諾**：場從來沒有拿過你的程式碼。

    tarball 快 8 倍（實測 2.0s vs 16.8s），但它會把整包下載再丟掉大部分
    ⇒ 那讓承諾退化成一句紀律。`history/131`：禁令做在結構上，不是紀律上。
    """

    def _src(self):
        import inspect

        from knowfield.github import app as ghapp
        from knowfield.web import app as webapp
        return inspect.getsource(ghapp) + inspect.getsource(webapp)

    def test_no_tarball_zipball_or_clone(self):
        import re
        code = re.sub(r"#.*$", "", self._src(), flags=re.M)      # 註解在解釋規則，別讓它絆倒自己
        code = re.sub(r'"""[\s\S]*?"""', "", code)
        for forbidden in ("tarball", "zipball", "git clone", "subprocess"):
            self.assertNotIn(forbidden, code, f"不該出現：{forbidden}")

    def test_only_knowledge_blobs_are_requested(self):
        """抓 blob 的那一段，前面一定站著一個 `knowledge/` 的過濾。"""
        import inspect

        from knowfield.github.app import GitHubApp
        body = inspect.getsource(GitHubApp.fetch)
        self.assertIn("KNOWLEDGE", body)
        self.assertLess(body.index("startswith(KNOWLEDGE)"), body.index("/git/blobs/"))


class TestFetchUsesTheRightBranch(unittest.TestCase):
    """⚠️ 對抗性驗證翻出來的空隙：上面的測試全餵**預先抓好的假資料**，
    於是 `fetch()` 真正的 branch 邏輯一次都沒被執行過——把 `default_branch`
    換成寫死的 `"main"`，16 條測試**全部照樣綠**。

    而實測 VizGPT 的預設分支是 `knowledge-python` ⇒ 寫死就是 404 或抓到錯的分支。
    這裡把 HTTP 那一層樁掉，斷言**實際請求的 URL**。
    """

    def _app(self, default_branch="knowledge-python", truncated=False):
        import base64

        from knowfield.github.app import GitHubApp
        calls = []
        tree = [
            {"type": "blob", "path": "README.md", "sha": "s1"},
            {"type": "blob", "path": "src/secret.py", "sha": "s2"},
            {"type": "blob", "path": "knowledge/experience.md", "sha": "s3"},
            {"type": "tree", "path": "knowledge", "sha": "s4"},
        ]

        def fake_get(path):
            calls.append(path)
            if path.startswith("/repos/") and path.count("/") == 3:
                return {"default_branch": default_branch, "private": True}
            if "/git/trees/" in path:
                return {"tree": tree, "truncated": truncated}
            if "/git/blobs/" in path:
                return {"content": base64.b64encode(b"# body").decode()}
            raise AssertionError(path)

        gh = GitHubApp(app_id="1", private_key=b"")
        gh._get = fake_get
        return gh, calls

    def test_uses_default_branch_not_main(self):
        gh, calls = self._app()
        out = gh.fetch("timcsy/VizGPT", workers=1)
        self.assertEqual(out["branch"], "knowledge-python")
        tree_calls = [c for c in calls if "/git/trees/" in c]
        self.assertEqual(len(tree_calls), 1)
        self.assertIn("knowledge-python", tree_calls[0])
        self.assertNotIn("/main?", tree_calls[0])

    def test_only_knowledge_blobs_are_actually_requested(self):
        """⚠️ 承諾的行為版：`src/secret.py` 的 sha **從來沒有被請求過**。"""
        gh, calls = self._app()
        gh.fetch("timcsy/VizGPT", workers=1)
        blobs = [c for c in calls if "/git/blobs/" in c]
        self.assertEqual(blobs, ["/repos/timcsy/VizGPT/git/blobs/s3"])
        self.assertFalse([c for c in calls if "s2" in c or "s1" in c])

    def test_tree_keeps_every_path_but_no_content(self):
        gh, _ = self._app()
        out = gh.fetch("timcsy/VizGPT", workers=1)
        self.assertEqual(sorted(out["paths"]),
                         ["README.md", "knowledge/experience.md", "src/secret.py"])
        self.assertEqual([i["path"] for i in out["items"]], ["knowledge/experience.md"])

    def test_truncated_flag_survives(self):
        gh, _ = self._app(truncated=True)
        self.assertTrue(gh.fetch("timcsy/VizGPT", workers=1)["truncated"])


class TestBasesPageScan(unittest.TestCase):
    """⚠️ 前端這半：**沒說樹多舊**的死指標報告，會被當成權威。掃原始碼釘住它。"""

    def setUp(self):
        import pathlib
        import re
        src = (pathlib.Path(__file__).resolve().parents[2]
               / "frontend/src/pages/BasesPage.tsx").read_text(encoding="utf-8")
        self.code = re.sub(r"/\*[\s\S]*?\*/", "", re.sub(r"//.*$", "", src, flags=re.M))

    def test_always_shows_how_old_the_tree_is(self):
        self.assertIn("fetched_at", self.code)
        self.assertIn("since(", self.code)

    def test_says_when_the_tree_was_truncated(self):
        self.assertIn("truncated", self.code)
        self.assertIn("截斷", self.code)

    def test_no_markdown_bold_in_plain_text(self):
        import re
        self.assertIsNone(re.search(r">\s*[^<]*\*\*[^<]*<", self.code))

    def test_does_not_call_it_your_knowledge(self):
        """⚠️ 外來的知識不能長得像你自己的——收進場是**另一個動作**（下一刀）。"""
        self.assertNotIn("你的理解", self.code)
        self.assertNotIn("收進", self.code)
