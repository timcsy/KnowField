"""文章進 /chat 視野的注入（spec 041）。零外呼——backend 注入。

⚠️ 本規格的重心不是功能而是**閘門**：文章是 AI 自己的產物，讓它回到 AI 的輸入，
形狀上就是 2026-08-07「文章永不回地基」防線要擋的東西。結構保證＝**文章只進臨時脈絡、
不進 `history`**，因此蒸餾冊封候選那一步（只吃 history）看不到它。
"""
from knowfield.chat.field_chat import FieldChat


class _Rec:
    """記錄送出的訊息。"""
    def __init__(self):
        self.sent = None

    def reply(self, messages):
        self.sent = messages
        return "回覆"


class _Root:
    def __init__(self, claim):
        self.claim = claim
        self.ladder = []


_ARTICLE = {"id": 7, "title": "擴散模型與流匹配",
            "markdown": "# 擴散模型\n\n這是一段只出現在文章裡的句子：藍鯨吃拉麵。\n"}
_MARK = "藍鯨吃拉麵"          # 只在文章裡出現 → 拿它當探針


def _msgs(fc, **kw):
    return fc._messages([], "我讀完想到一件事", [_Root("既有根因")], None,
                        kw.pop("bare", False), 20, **kw)


class TestArticleLayer:
    def test_article_appears_when_given(self):
        fc = FieldChat(_Rec())
        blob = str(_msgs(fc, article=_ARTICLE))
        assert _MARK in blob

    def test_absent_when_not_given(self):
        fc = FieldChat(_Rec())
        assert _MARK not in str(_msgs(fc))

    def test_unchanged_verbatim_when_not_given(self):
        """SC-004：沒選文章時，脈絡與現況**逐字相同**。"""
        fc = FieldChat(_Rec())
        before = fc._messages([], "問題", [_Root("r")], None, False, 20)
        after = fc._messages([], "問題", [_Root("r")], None, False, 20, article=None)
        assert before == after

    def test_marked_as_ai_derivative(self):
        """US2：標明是 AI 依核心理解生成的衍生物，且不得蓋過核心理解。"""
        fc = FieldChat(_Rec())
        blob = str(_msgs(fc, article=_ARTICLE))
        assert "AI" in blob
        assert "核心理解" in blob

    def test_separate_block_from_roots(self):
        """文章自成一層，不混進核心理解那段。"""
        fc = FieldChat(_Rec())
        ms = _msgs(fc, article=_ARTICLE)
        root_blocks = [m for m in ms if m["role"] == "system" and "既有根因" in m["content"]]
        assert root_blocks, "找不到核心理解區塊"
        for b in root_blocks:
            assert _MARK not in b["content"], "文章被混進核心理解區塊了"

    def test_bare_mode_excludes_article(self):
        """FR-007：bare＝屏蔽知識庫，而文章是知識庫的衍生物。"""
        fc = FieldChat(_Rec())
        assert _MARK not in str(_msgs(fc, article=_ARTICLE, bare=True))

    def test_length_capped(self):
        """FR-005：長文不得吃掉整個脈絡預算。"""
        fc = FieldChat(_Rec())
        big = {"id": 1, "title": "長", "markdown": "字" * 50000}
        blob = str(_msgs(fc, article=big))
        assert blob.count("字") < 10000


class TestGateArticleNeverEntersHistory:
    """⚠️ FR-003 的結構保證：文章不得進入 `history`。

    `distill()` 的輸入只由 `history` 串成，所以只要文章不進 history，
    蒸餾冊封候選那一步就**結構上**看不到它。
    """

    def test_article_only_ever_in_system_messages(self):
        """⚠️ 真正的不變式：文章只能出現在 `system` 訊息，**絕不在 user/assistant 回合**。

        會被持久化、之後餵進 `distill` 的正是 user/assistant 那些回合；system 訊息是
        每輪臨時組裝的、不落庫。所以「文章只在 system」就是那條結構保證。

        本測試改寫過一次：初版驗「呼叫端的 hist 沒被改」——但 `_messages` 開頭就
        `hist = list(history)` 複製了一份，那是**恆真命題**。拿「把文章 append 進 hist」
        的錯誤實作去撞，初版**全綠通過** ⇒ 它沒有在測任何東西。
        """
        fc = FieldChat(_Rec())
        hist = [{"role": "user", "content": "先前"}, {"role": "assistant", "content": "回覆"}]
        ms = fc._messages(hist, "現在", [_Root("r")], None, False, 20, article=_ARTICLE)
        for m in ms:
            if m["role"] != "system":
                assert _MARK not in m["content"], (
                    f"文章出現在 {m['role']} 回合——它會被持久化並流進 distill")

    def test_caller_history_not_mutated(self):
        fc = FieldChat(_Rec())
        hist = [{"role": "user", "content": "先前"}]
        before = [dict(m) for m in hist]
        fc._messages(hist, "現在", [_Root("r")], None, False, 20, article=_ARTICLE)
        assert hist == before

    def test_distill_input_has_no_article(self):
        """SC-003：蒸餾那一步的輸入中，文章內容出現次數＝0。"""
        rec = _Rec()
        fc = FieldChat(rec)
        hist = [{"role": "user", "content": "我讀完想到一件事"},
                {"role": "assistant", "content": "那我們往下推"}]
        fc.distill(hist, [])
        assert _MARK not in str(rec.sent), "文章洩進了蒸餾候選的輸入"
