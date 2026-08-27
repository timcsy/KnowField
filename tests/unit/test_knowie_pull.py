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


class TestPortableClaim(unittest.TestCase):
    """⚠️ 各個 base 的**私有記號**不能跟著判準跑到別人那裡去。

    實測（留一法，2026-08-27）：一個真的冷的專案會收到的 12 條裡，**4 條**帶著
    別的 base 的嚴重度標記（`⭐⭐`／`🔴🔴🔴`）與 HTML（`<u>`）。
    """

    def test_leading_severity_markers_are_stripped(self):
        for raw, want in [
            ("🔴🔴 一個檢查若會靜默失敗，它比沒有檢查更糟",
             "一個檢查若會靜默失敗，它比沒有檢查更糟"),
            ("⭐⭐ 一個判準失敗時，先問「門檻錯了」還是「數錯東西了」",
             "一個判準失敗時，先問「門檻錯了」還是「數錯東西了」"),
            ("⚠️ 把「失敗的出口」先寫進規格", "把「失敗的出口」先寫進規格"),
        ]:
            self.assertEqual(cc.lessons(_base(f"## 教訓\n\n### {raw}\n\n- 內文\n")), [want])

    def test_html_tags_are_stripped_anywhere(self):
        d = _base("## 教訓\n\n### 一個結論若只在一種排序下成立，那它是<u>排序</u>的性質\n\n- x\n")
        self.assertEqual(cc.lessons(d), ["一個結論若只在一種排序下成立，那它是排序的性質"])

    def test_meaningful_symbols_survive(self):
        """⚠️ `→ ≠ ⇒ ∃ ∀` 是**內容**——見到符號就剝會改掉判準本身。

        失敗方向要選對：剝不乾淨只是留一個記號，**剝過頭是改掉別人的話**。
        """
        for t in ["提案-批准 ≠ 打到需求",
                  "先問規則本身還對不對 ⇒ 別連著一起丟",
                  "從 A → B 的每一步都要留下為什麼"]:
            self.assertEqual(cc.lessons(_base(f"## 教訓\n\n### {t}\n\n- x\n")), [t])

    def test_meaningful_symbol_at_the_start_also_survives(self):
        """⚠️ 對抗性驗證翻出來的空隙：把箭頭／數學符號加進剝除類別，**沒有一條測試撞紅**
        ——因為上面那些案例的符號全在**句中**。真實資料今天剛好 0 條這種標題，
        所以這個洞今天無害；而**沒有人會發現它變壞**，那就是要釘住它的理由。
        """
        for t in ["⇒ 判準：問「這條如果錯了，誰會發現」",
                  "→ 從規格回推，不是從實作回推",
                  "≠ 不是同一件事：能跑 和 跑對"]:
            self.assertEqual(cc.lessons(_base(f"## 教訓\n\n### {t}\n\n- x\n")), [t])

    def test_marker_inside_the_sentence_is_not_a_decoration(self):
        """句中的 ⚠️ 是作者在強調，不是開頭的嚴重度標記 ⇒ 不動它。"""
        t = "一條規則寫下來的當天 ⚠️ 就會被自己違反一次"
        self.assertEqual(cc.lessons(_base(f"## 教訓\n\n### {t}\n\n- x\n")), [t])
