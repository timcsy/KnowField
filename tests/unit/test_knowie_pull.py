"""`knowie-pull`／`knowie-crosscheck`：借來的判準**不能**被算成獨立撞到。

⚠️ 這一條是使用者問「還是用 knowie-pull / knowie-push 比較好？」時翻出來的洞：
**「給」的那半一旦寫下去，「讀」的那半就開始說謊。**
`knowie-pull` 把借來的判準寫進新 base 的 `experience.md` 之後，
下一次跨 base 量測會把它讀成「這個 base 也獨立撞到了」——群數虛增、
排序被自己餵大，而**沒有任何東西會報錯**。draft §八 的原話：
「只算『撞到』，不算『借走』。否則推薦餵回計數、計數又餵回推薦——那就是馬太。」
"""
import importlib.util
import pathlib
import tempfile
import unittest

_XB = (pathlib.Path(__file__).resolve().parents[2]
       / "knowledge/skills/knowie-crosscheck/crosscheck.py")
_spec = importlib.util.spec_from_file_location("crosscheck", _XB)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

GROUP = {"claim": "一個檢查若會靜默失敗，它比沒有檢查更糟",
         "members": [{"base": "VizGPT", "text": "提醒不計為失敗＝沒有那道檢查"},
                     {"base": "semorphe", "text": "一個豁免沒有檢查，與漏洞沒有分別"}]}


def _base(body: str) -> pathlib.Path:
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "experience.md").write_text(body, encoding="utf-8")
    return d


class TestBorrowedIsNotAHit(unittest.TestCase):
    def test_round_trip_written_then_read_is_skipped(self):
        """⚠️ 核心：**同一支程式寫出來的東西，同一支程式讀不到。**

        產生器與讀取器共用 `BORROWED_MARK` 一個常數——各寫一份字串遲早會不一致，
        而不一致**不會報錯**，只會讓計數虛增。
        """
        d = _base("## 教訓\n\n" + cc.emit_lesson(GROUP))
        self.assertEqual(cc.lessons(d), [])

    def test_own_lessons_still_counted(self):
        """⚠️ 過濾不能順手把自己撞出來的也濾掉——那會讓複利看起來不存在。"""
        d = _base("## 教訓\n\n### 自己撞出來的一條判準\n\n- **來源**：commit abc123\n")
        self.assertEqual(cc.lessons(d), ["自己撞出來的一條判準"])

    def test_mixed_file_keeps_only_the_own_ones(self):
        d = _base("## 教訓\n\n### 自己撞出來的一條判準\n\n- **來源**：commit abc\n\n"
                  + cc.emit_lesson(GROUP)
                  + "\n### 另一條自己的判準\n\n- **來源**：commit def\n")
        self.assertEqual(cc.lessons(d), ["自己撞出來的一條判準", "另一條自己的判準"])

    def test_promoted_borrowed_counts_again(self):
        """撞到了才升格：把借來的那行換成實際出處 ⇒ 它**才開始**算這個 base 的經驗。"""
        block = cc.emit_lesson(GROUP)
        promoted = "\n".join(l for l in block.split("\n") if cc.BORROWED_MARK not in l)
        self.assertEqual(cc.lessons(_base("## 教訓\n\n" + promoted)), [GROUP["claim"]])

    def test_marker_does_not_leak_past_the_lesson(self):
        """⚠️ 標記只該影響**它自己那一條**——漏到下一條會靜默少算。"""
        d = _base("## 教訓\n\n" + cc.emit_lesson(GROUP)
                  + "\n### 借來的那條後面的自己人\n\n- **來源**：commit ghi\n")
        self.assertIn("借來的那條後面的自己人", cc.lessons(d))

    def test_section_break_also_ends_a_lesson(self):
        """`##` 換節也要結束一條——否則節與節之間的標記會跨節污染。"""
        d = _base("## 教訓\n\n" + cc.emit_lesson(GROUP)
                  + "\n## 關鍵延伸\n\n### 延伸裡的自己人\n\n- 內文\n")
        self.assertIn("延伸裡的自己人", cc.lessons(d))


class TestEmitShape(unittest.TestCase):
    def test_block_carries_where_it_came_from(self):
        b = cc.emit_lesson(GROUP)
        self.assertIn("`from: VizGPT, semorphe`", b)
        for m in GROUP["members"]:
            self.assertIn(m["text"], b)          # ⚠️ 給原文，不給分數
            self.assertIn(m["base"], b)
        self.assertNotIn("相似度", b)
        self.assertNotIn("0.6", b)

    def test_block_says_how_to_promote(self):
        """借來的要有一條**出得去**的路，否則它永遠是二等公民。"""
        self.assertIn("真的撞到之後", cc.emit_lesson(GROUP))

    def test_marker_appears_exactly_once(self):
        """⚠️ 對抗性驗證翻出來的真 bug：標記原本出現**兩次**（標記行 ＋ 升格說明）。

        照說明刪掉標記行的人，升格會失敗——另一處還在，量測照樣跳過它，
        而**沒有人會發現**。⇒ 升格這件事必須是「刪一行」就完成。
        """
        self.assertEqual(cc.emit_lesson(GROUP).count(cc.BORROWED_MARK), 1)

    def test_deleting_that_one_line_promotes_it(self):
        """把不變式接到行為上：刪掉**帶標記的那一行**，它就算數了。"""
        block = cc.emit_lesson(GROUP)
        promoted = "\n".join(l for l in block.split("\n")
                             if cc.BORROWED_MARK not in l)
        self.assertEqual(cc.lessons(_base("## 教訓\n\n" + promoted)), [GROUP["claim"]])
        self.assertIn("各自撞到的原文", promoted)      # 而原文要留著，別跟著一起沒了


class TestExclude(unittest.TestCase):
    def test_exclude_drops_that_base(self):
        """`knowie-pull` 問的是「**別人**獨立撞到什麼」——自己的不算證據。"""
        found = cc.find_bases([str(pathlib.Path(__file__).resolve().parents[3])])
        self.assertIn("KnowField", found)        # 掃得到才驗得了排除
