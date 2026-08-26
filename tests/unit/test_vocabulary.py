"""spec 053：改名不弄壞語意——「文章」是重載的。

⚠️ `field_chat` 的三層份量 prompt 裡有**兩種**「文章」：
  ① 「他收藏的**文章**/論文＝外部證言」——**別人寫的**，不是應用
  ② 「他自己知識庫生成的**文章**」——自家衍生物，就是應用

無腦全換會把 ① 也改掉，於是 prompt 變成把**外部來源**稱作使用者的應用
——⚠️ **而那壞掉的方式是沉默的**：模型仍會流暢作答，只是把別人的觀點當成他的地基。
沒有任何測試會因此變紅，除非有這一支。
"""
import unittest

from knowfield.chat import field_chat as fc_mod

SYSTEM_PROMPT = fc_mod._MEMBRANE


class TestVocabulary(unittest.TestCase):
    def test_understanding_is_called_理解_not_核心理解(self):
        """FR-006：使用者看得見的詞彙一律用「理解」。"""
        self.assertNotIn("核心理解", SYSTEM_PROMPT,
                         "系統 prompt 還在用舊詞——使用者看到的字要一致")

    def test_external_testimony_is_still_called_文章_or_論文(self):
        """⚠️ FR-008：外部證言那一層 MUST NOT 被改成「應用」。

        它是**別人寫的**。改了之後 prompt 會把外部來源歸進使用者的產出層，
        而模型不會報錯——它只會開始拿別人的觀點當他的地基。
        """
        self.assertIn("外部證言", SYSTEM_PROMPT)
        line = next(l for l in SYSTEM_PROMPT.splitlines() if "外部證言" in l)
        self.assertIn("論文", line, f"外部證言那一層被動到了：{line}")
        self.assertNotIn("應用", line,
                         f"⚠️ 把**別人寫的**東西稱作使用者的『應用』了：{line}")

    def test_the_three_layers_are_still_distinguishable(self):
        """三層份量要還在，而且彼此叫不同名字。"""
        self.assertIn("三層份量", SYSTEM_PROMPT)
        self.assertIn("地基", SYSTEM_PROMPT)
        self.assertIn("web", SYSTEM_PROMPT)

    def test_carried_own_output_is_called_應用(self):
        """FR-007：帶進來的自家生成物改稱「應用」，且仍說明它比理解軟。

        直接讀原始碼裡那段 prompt——它是 `build_messages` 就地組的字串。
        """
        import inspect
        src = inspect.getsource(fc_mod)
        seg = src[src.index("if article and not bare:"):src.index("# spec 042")]
        self.assertIn("應用", seg, "帶入的自家生成物還叫「文章」")
        self.assertNotIn("核心理解", seg, "還在用舊詞")
        self.assertIn("以理解為準", seg.replace("**", ""),
                      f"衝突時的優先序不見了：{seg[:200]}")


if __name__ == "__main__":
    unittest.main()
