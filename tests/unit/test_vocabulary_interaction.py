"""spec 061：對話 → 互動。⚠️ 「對話」是重載的，跟 spec 053 的「文章」同一族。

三種**不能改**的「對話」，每一種都不會有測試因此變紅——除非有這一支：

① **prompt 裡指「這一段來回」**——AI 跟你的來回**本來就是對話**，那個詞是對的。
   改成「互動」只會讓 LLM 更難懂它在講什麼，而且**不會有任何錯誤**。
② **外部意義**（登入頁「文章、論文、對話」）——那是**別人的東西**，不是我們的實體。
③ **動作**（「接著聊」）——改成「互動」反而更抽象。⇒ 實體名改，動作保留。
"""
import pathlib
import re
import unittest

from knowfield.chat import field_chat as fc
from knowfield.web import auth


class TestInteractionVocabulary(unittest.TestCase):
    # ── ①：prompt 裡的「這一段來回」逐字不動 ────────────────────

    def test_distill_prompt_still_says_對話(self):
        """蒸餾 prompt 講的是「以下這一段來回」——那就是對話。"""
        self.assertIn("對話", fc._DISTILL)

    def test_search_query_prompt_still_says_對話(self):
        self.assertIn("對話", fc._SEARCH_Q)

    def test_segment_prompt_untouched(self):
        """分章 prompt 也是在講那一段來回。"""
        self.assertIn("對話", fc._SEGMENT)

    # ── ②：外部意義的「對話」 ───────────────────────────────────

    def test_login_page_keeps_external_對話(self):
        """⚠️ 登入頁那句「文章、論文、對話」講的是**別人的東西**，不是我們的實體。

        改成「互動」的話，那句會變成「收進你信的來源——文章、論文、**互動**」，
        而使用者收進來的從來不是別人的互動。
        """
        line = next(l for l in auth.__dict__["_LOGIN_HTML"].splitlines()
                    if "收進你信的來源" in l) if "_LOGIN_HTML" in auth.__dict__ else ""
        src = open(auth.__file__, encoding="utf-8").read()
        line = next(l for l in src.splitlines() if "收進你信的來源" in l)
        self.assertIn("文章、論文、對話", line, f"外部意義的那句被動到了：{line.strip()[:80]}")
        self.assertNotIn("互動", line)

    # ── ③：實體名要改成「互動」 ────────────────────────────────

    def test_entity_facing_messages_use_互動(self):
        """使用者看得見的**實體**改叫互動。"""
        src = open("src/knowfield/web/app.py", encoding="utf-8").read()
        for probe in ("找不到那段互動", "這段互動還沒精選出理解"):
            self.assertIn(probe, src, f"實體名沒改到：{probe}")

    def test_no_stale_entity_wording_left(self):
        """⚠️ 改一半比不改更糟——這幾句是實體名，不該還留著「對話」。"""
        src = open("src/knowfield/web/app.py", encoding="utf-8").read()
        for stale in ("找不到那段對話", "這段對話還沒精選出理解", "找不到這段對話。"):
            self.assertNotIn(stale, src, f"還留著舊實體名：{stale}")


if __name__ == "__main__":
    unittest.main()


# ── 前端 ────────────────────────────────────────────────────────────────
# 放在 pytest 而不是 vitest：前端沒有 @types/node，為一支測試加依賴不划算，
# 而且詞彙規則的兩半（該改的／不能改的）放同一個檔，未來讀的人一次看得到。

# ⚠️ 絕對路徑，不是相對的：從別的目錄跑 pytest 時，相對路徑會掃到 0 個檔，
# 而「沒有陳舊字串」與「沒有掃到任何檔」長得**一模一樣**——測試照樣綠。
_SRC = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
_COMMENT = re.compile(r"^\s*(//|\*|/\*|\{/\*)|// |\*/")
# 白名單＝第 ① 類「這一段來回」，逐字保留
_ALLOWED = (re.compile("它讀起來像對話的開場白"), re.compile("依對話上下文判"))


def _user_visible_lines(word: str) -> list[str]:
    out, seen = [], 0
    for f in sorted(_SRC.rglob("*.ts*")):
        if "__tests__" in f.parts:        # 測試檔不是使用者看得見的字
            continue
        seen += 1
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if word in line and not _COMMENT.search(line):
                out.append(f"{f}:{i}: {line.strip()}")
    assert seen > 20, f"只掃到 {seen} 個前端檔——路徑錯了，這支測試等於沒在測"
    return out


class TestFrontendInteractionVocabulary(unittest.TestCase):
    def test_entity_labels_renamed(self):
        sidebar = (_SRC / "components/ConversationSidebar.tsx").read_text(encoding="utf-8")
        self.assertIn('label: "💬 互動"', sidebar)
        self.assertIn("＋ 新互動", sidebar)
        self.assertIn('conversation: "💬 互動"',
                      (_SRC / "pages/DomainsPage.tsx").read_text(encoding="utf-8"))

    def test_no_half_rename(self):
        """⚠️ 留一句舊的比全部不改更難讀——這條會把漏掉的那一行印出來。"""
        stale = [l for l in _user_visible_lines("對話")
                 if not any(a.search(l) for a in _ALLOWED)]
        self.assertEqual(stale, [], "還留著舊實體名：\n" + "\n".join(stale))

    def test_this_exchange_meaning_kept(self):
        """第 ① 類：KindBadge 的「對話上下文」講的是那一段來回，不能改。"""
        self.assertIn("依對話上下文判",
                      (_SRC / "components/KindBadge.tsx").read_text(encoding="utf-8"))
