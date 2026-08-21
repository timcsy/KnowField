"""spec 042：帶入來源的分層注入。零外呼——只檢查組出來的 messages。"""
import unittest

from knowfield.chat.field_chat import FieldChat


class _Backend:
    def reply(self, messages): return ""
    def stream(self, messages): yield ""


def _fc():
    return FieldChat(_Backend())


_SRC = {"url": "https://x/1", "title": "Neural Networks and Topology",
        "body": "Recently there has been a great deal of excitement about deep neural networks.",
        "total_units": 3, "shown_units": 3, "excerpted": False}


def _msgs(**kw):
    fc = _fc()
    base = dict(history=[], user_msg="這篇在講什麼", roots=[], sources=None,
                bare=False, max_history=0)
    base.update(kw)
    return fc._messages(**base)


def _text(msgs):
    return "\n".join(m["content"] for m in msgs)


class TestSourceInjection(unittest.TestCase):
    def test_source_body_reaches_the_model(self):
        """FR-003：帶入就一定進脈絡，不看撒網臉色。"""
        self.assertIn("great deal of excitement", _text(_msgs(source=_SRC)))

    def test_source_never_enters_history(self):
        """脈絡衛生（沿用 041 的形狀）：來源只出現在這裡組的臨時訊息裡。
        ⚠️ 但這**不是** 041 FR-003 那道閘門——來源不是 AI 產物，
        從來源冊封是既有的合法功能（spec 042 FR-010）。"""
        hist = [{"role": "user", "content": "先前一句"}]
        _msgs(history=hist, source=_SRC)
        self.assertEqual(hist, [{"role": "user", "content": "先前一句"}])

    def test_bare_does_not_inject(self):
        """FR-008。"""
        self.assertNotIn("great deal of excitement", _text(_msgs(source=_SRC, bare=True)))

    def test_no_source_is_byte_identical(self):
        """⚠️ FR-011／SC-007：沒帶來源時，訊息與現況**逐字相同**。

        ⚠️ 第一版寫成 `_msgs(source=None) == _msgs()` ——那是**同義反覆**：
        兩邊跑的是同一份程式碼，多塞幾則訊息也照樣相等（反向攻擊撞不動）。
        要有牙齒就得比對**寫死的預期結構**，而不是拿自己比自己。
        這是同一個坑的第三次（spec 041 的 `hist = list(history)` 是第二次）。
        """
        msgs = _msgs(source=None)
        self.assertEqual([m["role"] for m in msgs], ["system", "user"],
                         "空 history／roots／sources 時就只該有 system ＋ user 兩則")
        self.assertEqual(msgs[-1], {"role": "user", "content": "這篇在講什麼"})
        self.assertNotIn("收進的來源", msgs[0]["content"])

    def test_excerpt_is_declared(self):
        """FR-005：節錄要明講共幾段、給了幾段，模型才不會把沒看到的當作不存在。"""
        s = dict(_SRC, excerpted=True, total_units=45, shown_units=6)
        t = _text(_msgs(source=s))
        self.assertIn("45", t)
        self.assertIn("6", t)

    def test_original_vs_displayed_is_declared(self):
        """FR-004：無條件講一句永遠為真的話——使用者看到的可能是轉換後的版本，這裡給的是原文。"""
        t = _text(_msgs(source=_SRC))
        self.assertIn("原文", t)

    def test_source_is_labeled_first_hand(self):
        """FR-006：一手素材，與 roots、與文章分層。"""
        self.assertIn("收進", _text(_msgs(source=_SRC)))
