"""spec 071：跨 base 判準的收件匣。

⚠️ 這一刀最容易安靜壞掉的兩處：
1. **略過的又冒出來**——去重若跟著 `_LIVE` 走，封存過的候選下次匯入就復活，
   於是每次匯入都要重看一遍同樣的東西，而畫面上一切正常。
2. **收下了卻沒進檢索語料**——清單看得到、聊天用不到（跟 spec 062 FR-005 同一個洞）。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db

G1 = {"claim": "警告不是實作",
      "members": [{"base": "KnowField", "text": "寫了警告但沒有實作，等於沒做"},
                  {"base": "VizGPT", "text": "註解說會擋，程式沒擋"},
                  {"base": "wewayfinders", "text": "文件寫了規則，沒有人在執行"}]}
G2 = {"claim": "量測工具會說謊",
      "members": [{"base": "KnowField", "text": "門檻沒校驗就下結論"},
                  {"base": "semorphe", "text": "量了一件錯的事"}]}


class Base(unittest.TestCase):
    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)

    def repo(self):
        return Repository(self.db)

    def imp(self, *groups):
        return self.c.post("/api/borrowed/import", json={"groups": list(groups)})


class TestImportLandsInInbox(Base):
    """驗收 1：匯入 N 群 → 收件匣 N 條，每條看得出跨哪幾個 base 與成員原文。"""

    def test_lands_as_candidate_not_anointed(self):
        self.imp(G1, G2)
        d = self.c.get("/api/roots").json()
        self.assertEqual(len(d["candidates"]), 2)
        # ⚠️ 匯入**不等於收下**——一條都不該直接進「你的理解」
        self.assertEqual(d["anointed"], [])

    def test_shows_which_bases_it_spans(self):
        self.imp(G1)
        w = self.c.get("/api/roots").json()["candidates"][0]
        self.assertEqual(w["origin"], "from:KnowField,VizGPT,wewayfinders")
        self.assertEqual(Repository.borrowed_bases(w["origin"]),
                         ["KnowField", "VizGPT", "wewayfinders"])

    def test_shows_member_verbatim_text(self):
        """⚠️ **給原文，不要給分數**——複審要能像肉眼校驗那樣判斷。"""
        self.imp(G1)
        w = self.c.get("/api/roots").json()["candidates"][0]
        self.assertEqual(len(w["ladder"]), 3)
        joined = "\n".join(w["ladder"])
        for m in G1["members"]:
            self.assertIn(m["text"], joined)       # 原文逐字在
            self.assertIn(m["base"], joined)       # 而且看得出來自哪個 base

    def test_borrowed_is_marked_borrowed(self):
        """FR-001：在這個場真的撞到之前，它**不算你自己撞出來的**。"""
        self.imp(G1)
        w = self.c.get("/api/roots").json()["candidates"][0]
        self.assertTrue(w["origin"].startswith(Repository.BORROWED))
        self.assertNotIn(w["origin"], ("", "self", "self:judgment"))


class TestAnoint(Base):
    def test_anointing_keeps_the_borrowed_mark(self):
        """FR-006：收下之後仍看得出它是借來的——冊封只改狀態。"""
        self.imp(G1)
        wid = self.c.get("/api/roots").json()["candidates"][0]["id"]
        self.c.post("/api/whynode/anoint", json={"id": wid})
        d = self.c.get("/api/roots").json()
        self.assertEqual(d["candidates"], [])
        self.assertEqual(d["anointed"][0]["origin"], "from:KnowField,VizGPT,wewayfinders")

    def test_anointed_enters_retrieval_corpus(self):
        """⚠️ 驗收 2：收下的**進得了檢索語料**——否則寫進去了卻不在你的場裡。"""
        self.imp(G1)
        wid = self.c.get("/api/roots").json()["candidates"][0]["id"]
        r = self.repo()
        self.assertNotIn("警告不是實作", " ".join(
            e.body for e in r.list_corpus_entries()))          # 候選階段：還不在場裡
        r.close()
        self.c.post("/api/whynode/anoint", json={"id": wid})
        r = self.repo()
        self.assertIn("警告不是實作", " ".join(
            e.body + e.headline for e in r.list_corpus_entries()))
        r.close()

    def test_can_rewrite_the_claim_when_anointing(self):
        """⚠️ **不合成**：合併成自己的話是**人**的事，介面本來就讓他改。"""
        self.imp(G1)
        wid = self.c.get("/api/roots").json()["candidates"][0]["id"]
        self.c.post("/api/whynode/anoint", json={"id": wid, "claim": "寫下的警告不會自己執行"})
        self.assertEqual(self.c.get("/api/roots").json()["anointed"][0]["claim"],
                         "寫下的警告不會自己執行")


class TestSkippedStaysSkipped(Base):
    """⚠️ FR-005／驗收 3：略過的**不再出現**，否則每次匯入都重看一遍。"""

    def test_reimport_after_skip_does_not_resurrect(self):
        self.imp(G1, G2)
        wid = self.c.get("/api/roots").json()["candidates"][0]["id"]
        self.c.post("/api/whynode/remove", json={"id": wid})     # 略過＝退回（既有動作）
        self.assertEqual(len(self.c.get("/api/roots").json()["candidates"]), 1)
        r = self.imp(G1, G2).json()
        self.assertEqual(r["added"], 0)
        self.assertEqual(r["skipped"], 2)
        self.assertEqual(len(self.c.get("/api/roots").json()["candidates"]), 1)

    def test_reimport_does_not_duplicate_the_anointed(self):
        self.imp(G1)
        wid = self.c.get("/api/roots").json()["candidates"][0]["id"]
        self.c.post("/api/whynode/anoint", json={"id": wid})
        self.imp(G1)
        d = self.c.get("/api/roots").json()
        self.assertEqual(len(d["anointed"]) + len(d["candidates"]), 1)

    def test_reimport_after_rewriting_the_claim_does_not_duplicate(self):
        """⚠️ 這條是**實跑**抓到的，單元測試原本漏掉。

        冊封時把它改寫成自己的話——**設計鼓勵的事**——之後 claim 就跟原本那群對不上，
        下次匯入整群復活。上一條測試冊封時沒改寫，所以綠得毫無意義：
        「一條沒有被錯誤實作撞過的測試，不知道自己在測什麼」。
        """
        self.imp(G1)
        wid = self.c.get("/api/roots").json()["candidates"][0]["id"]
        self.c.post("/api/whynode/anoint",
                    json={"id": wid, "claim": "寫下的警告不會自己執行"})
        r = self.imp(G1).json()
        self.assertEqual(r["added"], 0)
        d = self.c.get("/api/roots").json()
        self.assertEqual(len(d["anointed"]) + len(d["candidates"]), 1)

    def test_reimport_after_rewriting_a_skipped_one_does_not_resurrect(self):
        """略過的那半也一樣——只是它沒有改寫的機會，所以靠 ladder 也擋得住。"""
        self.imp(G2)
        wid = self.c.get("/api/roots").json()["candidates"][0]["id"]
        self.c.post("/api/whynode/remove", json={"id": wid})
        self.assertEqual(self.imp(G2).json()["added"], 0)

    def test_duplicate_within_one_batch_lands_once(self):
        r = self.imp(G1, dict(G1)).json()
        self.assertEqual((r["added"], r["skipped"]), (1, 1))


class TestGarbageIn(Base):
    def test_empty_claim_or_no_members_is_skipped_not_crashed(self):
        r = self.imp({"claim": "", "members": [{"base": "a", "text": "x"}]},
                     {"claim": "有主張但沒成員", "members": []},
                     {"claim": "成員是空的", "members": [{"base": " ", "text": " "}]},
                     G1).json()
        self.assertEqual((r["added"], r["skipped"]), (1, 3))

    def test_groups_must_be_a_list(self):
        self.assertEqual(self.c.post("/api/borrowed/import", json={"groups": "G1"}).status_code, 400)


class TestNoBulkAccept(Base):
    """⚠️ 驗收 4：路由表裡**沒有任何一次收多條的路徑**（沿用 spec 065／069 的結構性禁令）。

    這條測試掃的是**路由表**，不是 UI——按鈕拿掉很容易，端點留著才是真正的洞。
    """

    def test_no_route_accepts_many(self):
        import inspect

        from knowfield.web import app as appmod
        src = inspect.getsource(appmod)
        for r in self.app.routes:
            path = getattr(r, "path", "")
            if "anoint" not in path:
                continue
            fn = getattr(r, "endpoint", None)
            body = inspect.getsource(fn) if fn else ""
            self.assertNotIn("ids", body,
                             f"{path} 看起來吃複數 id——收下必須一條一條")
        # ⚠️ 別釘一個**具體的函式名**——改名就悄悄失效了（`api_xbase_accept_all`
        #    在 2026-08-27 改名後就是一個永遠不會出現的字串）。釘**形狀**。
        import re
        self.assertIsNone(re.search(r"def \w*(anoint|accept)_(all|many|bulk)", src))


class TestIsolation(Base):
    """驗收 5：換一個 owner／分身 → 看不到。

    ⚠️ 這裡差點寫成一條**假測試**：spec 067 的設計是 `persona_id IS NULL` ＝ **共用**
    （「預設共用，隔離是選擇」）。用預設 repo 匯入本來就是共用的，
    所以「另一個分身看不到」在那個前提下是錯的期待——要**在某個分身底下匯入**才驗得到隔離。
    """

    def test_imported_under_a_persona_stays_in_that_persona(self):
        r = self.repo()
        a, b = r.create_persona("分身甲"), r.create_persona("分身乙")
        r.close()
        self.c.cookies.set("kf_persona", str(a))
        self.imp(G1)
        self.c.cookies.set("kf_persona", str(b))
        self.assertEqual(self.c.get("/api/roots").json()["candidates"], [])
        self.c.cookies.set("kf_persona", str(a))
        self.assertEqual(len(self.c.get("/api/roots").json()["candidates"]), 1)

    def test_another_owner_cannot_see_the_inbox(self):
        self.imp(G1)
        other = Repository(self.db, owner=999)
        self.assertEqual(other.list_why_nodes("candidate"), [])
        other.close()

    def test_shared_import_is_visible_to_every_persona(self):
        """預設匯入（無分身）＝**共用**——這是設計，不是漏洞（spec 067）。"""
        self.imp(G1)
        r = self.repo(); pid = r.create_persona("分身丙"); r.close()
        self.c.cookies.set("kf_persona", str(pid))
        self.assertEqual(len(self.c.get("/api/roots").json()["candidates"]), 1)


class TestInboxUiScan(unittest.TestCase):
    """⚠️ 前端這半掃**原始碼**——按鈕拿掉很容易，行為留著才是洞。

    ⓘ 掃描器放在 Python 這邊，跟既有的 markdown 洩漏掃描同一個地方
    （放 vitest 那邊 `tsc -b` 會因為 `node:fs` 沒有型別而紅——
    而 vitest 是綠的，那正是「兩條管線不是同一條」的老陷阱）。
    """

    def setUp(self):
        import pathlib
        import re
        src = (pathlib.Path(__file__).resolve().parents[2]
               / "frontend/src/components/BorrowedInbox.tsx").read_text(encoding="utf-8")
        # 註解正是在**解釋這些規則**，留著會讓每條規則被自己絆倒
        self.code = re.sub(r"/\*.*?\*/", "", re.sub(r"//.*$", "", src, flags=re.M), flags=re.S)

    def test_no_bulk_accept_button(self):
        """驗收 4 的前端那半：迴圈打 anoint 在資料上等價於「全部收下」，而且看不出來。"""
        import re
        self.assertIsNone(re.search(r"\.map\([^)]*=>[^)]*whynodeAnoint", self.code))
        self.assertNotIn("全部收下", self.code)
        self.assertNotIn("一次收下", self.code)

    def test_no_similarity_score_shown(self):
        """⚠️ **給原文，不要給分數**——相似度是篩子不是判準，而分數不可反駁。"""
        for token in ("相似度", "similarity", "toFixed("):
            self.assertNotIn(token, self.code)

    def test_shows_provenance(self):
        self.assertIn("borrowedBases", self.code)
        self.assertIn("借來的", self.code)
