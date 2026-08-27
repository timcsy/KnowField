"""spec 073：場自己算跨 base 群 → 落進既有的收件匣。

⚠️ 這一刀最容易安靜壞掉的四處：
1. **借來的被算成獨立撞到** —— 計數餵回推薦、推薦餵回計數，那就是馬太。
2. **沒有校驗配對卻給了群** —— 一個沒校驗的門檻會給你看起來很專業的錯結論。
3. **只回一個界** —— 校驗給上界、最大群給下界；只量一邊比不量更難懷疑。
4. **繞過收件匣直接進場** —— 原則 6：只有沉澱物入場，守門在膜上。
"""
import unittest

from fastapi.testclient import TestClient

from knowfield.organize import crossbase as cb
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


def _exp(*titles):
    body = "## 教訓\n\n" + "".join(f"### {t}\n\n- 內文\n\n" for t in titles)
    return {"path": "knowledge/experience.md", "layer": "experience", "body": body}


class TestExtract(unittest.TestCase):
    def test_strips_other_bases_private_markup(self):
        self.assertEqual(cb.lessons_from([_exp("🔴🔴 一個檢查若會靜默失敗")]),
                         ["一個檢查若會靜默失敗"])

    def test_meaningful_symbols_survive(self):
        for t in ["提案-批准 ≠ 打到需求", "⇒ 判準：問誰會發現"]:
            self.assertEqual(cb.lessons_from([_exp(t)]), [t])

    def test_borrowed_is_not_an_independent_hit(self):
        """⚠️ FR-003：只算「撞到」，不算「借走」。"""
        body = ("## 教訓\n\n### 借來的那一條判準\n\n- " + cb.BORROWED_MARK
                + "（`from: A, B`）\n\n### 自己撞出來的那一條\n\n- 來源：commit abc\n")
        got = cb.lessons_from([{"path": "knowledge/experience.md",
                                "layer": "experience", "body": body}])
        self.assertEqual(got, ["自己撞出來的那一條"])   # ⓘ 標題要 ≥6 字才算（承自 skill 的過濾）

    def test_concept_filenames_are_claims(self):
        """ⓘ 根公理 1：一個概念，多個投影 ⇒ 概念層撞到比教訓層強。"""
        got = cb.lessons_from([
            {"path": "knowledge/concepts/複述一份真相就是排定它過期的日子.md",
             "layer": "concepts", "body": ""},
            {"path": "knowledge/concepts/README.md", "layer": "concepts", "body": ""}])
        self.assertEqual(got, ["複述一份真相就是排定它過期的日子"])

    def test_other_layers_are_not_lessons(self):
        """history 的標題是**轉移**不是判準；draft 是未定的。"""
        self.assertEqual(cb.lessons_from([
            {"path": "knowledge/history/1-x.md", "layer": "history", "body": "### 標題\n"},
            {"path": "knowledge/draft/d.md", "layer": "draft", "body": "### 標題\n"}]), [])


class TestGroupAndCalibrate(unittest.TestCase):
    def _vec(self, mapping):
        return mapping

    def test_groups_need_two_distinct_bases(self):
        v = {"a1": [1.0, 0.0], "a2": [1.0, 0.0], "b1": [1.0, 0.0]}
        one = cb.group({"A": ["a1", "a2"]}, v, 0.5)
        two = cb.group({"A": ["a1"], "B": ["b1"]}, v, 0.5)
        self.assertEqual(one["n_groups"], 0)        # 同一個 base 內部不算
        self.assertEqual(two["n_groups"], 1)

    def test_largest_is_returned(self):
        """⚠️ FR-005 的下界訊號——沒有它就只量了一邊。"""
        v = {f"x{i}": [1.0, 0.0] for i in range(6)}
        g = cb.group({"A": ["x0", "x1", "x2"], "B": ["x3", "x4", "x5"]}, v, 0.5)
        self.assertEqual(g["largest"], 6)

    def test_calibrate_returns_both_bounds(self):
        v = {"p": [1.0, 0.0], "q": [0.95, 0.312], "r": [0.0, 1.0]}
        c = cb.calibrate(v, [("A", "p"), ("B", "r")], [("p", "q")])
        self.assertIn("noise_hi", c)          # 上界：已知答案
        self.assertIn("floor", c)             # 下界訊號由 group() 的 largest 給
        self.assertAlmostEqual(c["floor"], 0.95, places=2)
        self.assertLess(c["noise_hi"], c["floor"])   # 噪音要明顯低於已知配對

    def test_representative_is_not_synthesised(self):
        """⚠️ 不合成：代表句一定是**某個 base 真的寫過**的那一句。"""
        v = {"短的": [1.0, 0.0], "比較長的那一句話": [1.0, 0.0]}
        g = cb.group({"A": ["短的"], "B": ["比較長的那一句話"]}, v, 0.5)
        self.assertIn(g["groups"][0]["claim"], ("短的", "比較長的那一句話"))


class Wired(unittest.TestCase):
    """接上資料層與收件匣。用固定向量的離線 embedder。"""

    def setUp(self):
        self.db = temp_db()
        self.app = build_app(self.db)
        self.c = TestClient(self.app)

    def seed(self, repo, titles, concepts=()):
        r = Repository(self.db)
        bid = r.add_ext_base(repo)
        items = [_exp(*titles)] + [
            {"path": f"knowledge/concepts/{n}.md", "layer": "concepts", "body": ""}
            for n in concepts]
        r.save_ext_fetch(bid, {"branch": "main", "private": False, "truncated": False,
                               "paths": [i["path"] for i in items], "items": items})
        r.close()
        return bid

    def test_lessons_sync_keeps_existing_vectors(self):
        """⚠️ 重算不該把已經花錢算好的向量丟掉——不然沒有人願意按第二次。"""
        bid = self.seed("t/A", ["第一條判準句", "第二條判準句"])
        r = Repository(self.db)
        r.sync_ext_lessons(bid, ["第一條判準句", "第二條判準句"])
        r.save_ext_vectors([(m["id"], [1.0, 0.0])
                            for m in r.ext_lessons_missing_vectors("T")], "T")
        r.sync_ext_lessons(bid, ["第一條判準句", "第三條判準句"])   # 一去一留一新
        left = {m["text"] for m in r.ext_lessons_missing_vectors("T")}
        bases, vec = r.ext_lesson_vectors("T")
        r.close()
        self.assertEqual(left, {"第三條判準句"})            # 只有新的要算
        self.assertEqual(list(vec), ["第一條判準句"])        # 舊的向量還在

    def test_isolation(self):
        self.seed("t/A", ["一條判準句"])
        other = Repository(self.db, owner=999)
        self.assertEqual(other.ext_items_of(1), [])
        self.assertEqual(other.ext_lesson_vectors("T"), ({}, {}))
        other.close()


class TestNoBypass(unittest.TestCase):
    """⚠️ FR-006：群一定落進**收件匣**，不直接進場。原則 6：守門在膜上。"""

    def test_import_goes_through_the_inbox(self):
        import inspect

        from knowfield.web import app as mod
        src = inspect.getsource(mod)
        i = src.index("def _crosscheck")
        body = src[i:src.index("@app.post(\"/api/bases/crosscheck\")")]
        self.assertIn("import_borrowed", body)
        self.assertNotIn("anoint_why_node", body)   # 不自己冊封

    def test_refuses_without_calibration(self):
        """⚠️ FR-004：結構性禁令，不是提醒。"""
        import inspect

        from knowfield.web import app as mod
        src = inspect.getsource(mod)
        i = src.index("def _crosscheck")
        self.assertIn('if not cal["calibration"]',
                      src[i:src.index("@app.post(\"/api/bases/crosscheck\")")])
