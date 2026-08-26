"""spec 067：persona——隱私的**硬**隔離。

⚠️ 它跟領域的差別是軟／硬：領域是過濾（隨時可以「在整個知識庫找」），
persona 是隔離（**沒有後門**，不然它就不是隱私）。
所以這裡最重要的不是「切得過去」，是**「切過去就真的看不到」**——含搜尋。
"""
import unittest
from datetime import datetime, timezone

from knowfield.store.repository import Repository
from tests.web_helpers import temp_db

_NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        r = Repository(self.db)
        self.work = r.create_persona("工作")
        self.life = r.create_persona("私人")
        # 共用（沒有身分時建的）
        w = r.add_why_node("這條是共用的判準", [], [], False, 0, _NOW)
        r.anoint_why_node(w)
        r.close()
        rw = Repository(self.db, persona=self.work)
        wid = rw.add_why_node("只有工作看得到的事", [], [], False, 0, _NOW)
        rw.anoint_why_node(wid)
        rw.close()
        # ⚠️ 第三件是必要的：只有共用＋工作兩件的話，工作身分「看得到全部」是真的，
        #    而那會讓 test_no_see_everything_mode 沒牙——它會分不出隔離成不成立。
        rl = Repository(self.db, persona=self.life)
        lid = rl.add_why_node("只有私人看得到的事", [], [], False, 0, _NOW)
        rl.anoint_why_node(lid)
        rl.close()


class TestHardIsolation(Base):
    def test_shared_is_visible_everywhere(self):
        """FR-002：**預設共用**——共用的東西每個身分都拿得到。"""
        for p in (None, self.work, self.life):
            r = Repository(self.db, persona=p)
            claims = [w.claim for w in r.list_why_nodes("anointed")]
            r.close()
            self.assertIn("這條是共用的判準", claims, f"persona={p} 看不到共用層")

    def test_other_persona_is_invisible(self):
        r = Repository(self.db, persona=self.life)
        claims = [w.claim for w in r.list_why_nodes("anointed")]
        r.close()
        self.assertNotIn("只有工作看得到的事", claims)

    def test_search_cannot_cross_persona(self):
        """⚠️ 搜尋是最容易漏掉硬邊界的地方（spec 066 同一條）。"""
        r = Repository(self.db, persona=self.life)
        hits = [h["label"] for h in r.search("只有工作")]
        r.close()
        self.assertEqual(hits, [], "換個身分還搜得到——那就不是隔離")

    def test_corpus_cannot_cross_persona(self):
        """⚠️ 比畫面更要緊：**別人身分的理解在回答你的問題**，而畫面上毫無跡象。"""
        r = Repository(self.db, persona=self.life)
        bodies = " ".join(e.body for e in r._anointed_corpus_entries())
        r.close()
        self.assertNotIn("只有工作看得到的事", bodies)

    def test_no_see_everything_mode(self):
        """FR-004：⚠️ **沒有「看全部」**。有後門就不是硬隔離。

        沒指定身分＝只看共用；指定身分＝共用 ＋ 那一個。兩者都看不到「全部」。
        """
        seen = set()
        for p in (None, self.work, self.life):
            r = Repository(self.db, persona=p)
            seen |= {w.claim for w in r.list_why_nodes("anointed")}
            r.close()
        # 聯集當然看得到全部——但**沒有任何單一個 repo** 看得到全部
        for p in (None, self.work, self.life):
            r = Repository(self.db, persona=p)
            claims = {w.claim for w in r.list_why_nodes("anointed")}
            r.close()
            self.assertNotEqual(claims, seen, f"persona={p} 看到了全部")


class TestWritesGoToCurrent(Base):
    def test_new_things_belong_to_current_persona(self):
        r = Repository(self.db, persona=self.life)
        wid = r.add_why_node("私人的一條", [], [], False, 0, _NOW)
        row = r.conn.execute("SELECT persona_id FROM why_nodes WHERE id=%s", (wid,)).fetchone()
        r.close()
        self.assertEqual(row["persona_id"], self.life)

    def test_no_persona_writes_shared(self):
        r = Repository(self.db)
        wid = r.add_why_node("沒身分時寫的", [], [], False, 0, _NOW)
        row = r.conn.execute("SELECT persona_id FROM why_nodes WHERE id=%s", (wid,)).fetchone()
        r.close()
        self.assertIsNone(row["persona_id"], "沒有身分時寫的東西應該留在共用層")


class TestPersonaList(Base):
    def test_list_and_create(self):
        r = Repository(self.db)
        names = [p["name"] for p in r.list_personas()]
        r.close()
        self.assertEqual(names, ["工作", "私人"])

    def test_personas_are_per_owner(self):
        r2 = Repository(self.db, owner=2)
        self.assertEqual(r2.list_personas(), [])
        r2.close()


if __name__ == "__main__":
    unittest.main()


class TestPersonaApi(unittest.TestCase):
    """API 層：切換靠 cookie，而**每一個請求**都要照它過濾。"""

    def setUp(self):
        from fastapi.testclient import TestClient
        from tests.web_helpers import build_app
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)
        self.work = self.c.post("/api/personas", json={"name": "工作"}).json()["id"]
        self.c.post("/api/personas/switch", json={"id": self.work})
        self.c.post("/api/understanding/write",
                    json={"claim": "工作身分寫的一條", "origin": "self:judgment"})

    def test_visible_in_that_persona(self):
        got = [w["claim"] for w in self.c.get("/api/roots").json()["anointed"]]
        self.assertIn("工作身分寫的一條", got)

    def test_invisible_after_switching_away(self):
        self.c.post("/api/personas/switch", json={"id": None})
        got = [w["claim"] for w in self.c.get("/api/roots").json()["anointed"]]
        self.assertNotIn("工作身分寫的一條", got, "切回共用層還看得到——那不是隔離")

    def test_search_also_respects_it(self):
        """⚠️ 搜尋那條路最容易漏——它天生就是「把全部撈出來」。"""
        self.c.post("/api/personas/switch", json={"id": None})
        g = self.c.get("/api/search", params={"q": "工作身分"}).json()["groups"]
        self.assertEqual(g, [])

    def test_bogus_cookie_falls_back_to_shared(self):
        """⚠️ 亂填的 cookie 最壞只會看到共用層，不會看到別人的。"""
        self.c.cookies.set("kf_persona", "999999")
        got = [w["claim"] for w in self.c.get("/api/roots").json()["anointed"]]
        self.assertNotIn("工作身分寫的一條", got)


class TestNoMarkdownInPlainTextUi(unittest.TestCase):
    """⚠️ 這個錯犯第二次了（spec 065 的區理由也漏過星號）。

    介面是**純文字渲染**，`**粗體**` 會原樣長在畫面上。
    而它不是文案瑕疵：讀起來像機器湊的 ⇒ 不可信 ⇒ 那句話就白寫了。
    """

    def test_frontend_plaintext_has_no_markdown_bold(self):
        import pathlib
        import re
        root = pathlib.Path(__file__).resolve().parents[2] / "frontend/src"
        bad = []
        for f in sorted(root.rglob("*.tsx")):
            in_comment = False
            for i, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
                st = line.strip()
                # ⚠️ 多行 JSX 註解的**續行**不以 // 或 * 開頭——第一版掃描器就是這樣誤報的
                if "{/*" in line or "/*" in line:
                    in_comment = True
                was_comment = in_comment
                if "*/" in line:
                    in_comment = False
                if was_comment or st.startswith("//") or "//" in line:
                    continue                      # 註解裡的粗體是給人讀的，不會進畫面
                if re.search(r"\*\*[^*]+\*\*", line):
                    bad.append(f"{f.name}:{i}: {st[:80]}")
        self.assertEqual(bad, [], "markdown 星號會原樣長在畫面上：\n" + "\n".join(bad))
