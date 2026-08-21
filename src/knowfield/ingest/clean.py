"""LLM 深度清理貼上內容（spec 031 US4，選用）。

結構抽取擋不掉的雜訊（穿插的推薦/標籤/評論）交給 LLM。**捕捉工具的鐵律：只剝雜訊、逐字保留正文、
不改寫**——嚴格 prompt＋失敗退回原文（教訓 3 best-effort）。可注入 backend、離線可測。
"""

from __future__ import annotations

_CLEAN = (
    "以下是使用者從網頁複製貼上的內容，夾雜導覽、推薦、廣告、評論、按鈕、UI 等**非正文雜訊**。\n"
    "請輸出**乾淨的正文 markdown**。鐵律：\n"
    "1. **逐字保留正文**——不要改寫、不要摘要、不要翻譯、不要新增任何內容。\n"
    "2. 只做兩件事：**刪掉明顯的非正文雜訊**、給正文基本 markdown 結構（標題/段落/清單/圖片）。\n"
    "3. 保留原有的圖片語法 `![](...)`。\n"
    "4. 看到 `@@KFPROTECT<數字>@@` 這種佔位符，**原封不動照抄、位置不變**、不要動它。\n"
    "只輸出正文 markdown，不要說明。")


def clean_markdown(text: str, backend) -> str:
    """用 LLM 剝雜訊、逐字留正文。backend 為 None／失敗→退回原文（best-effort）。"""
    if backend is None or not (text or "").strip():
        return text
    # ⚠️ 承重內容（數學／程式碼／URL／圖片）先抽佔位再送出去。
    # 這裡原本只靠提示詞「逐字保留正文」——但這個庫自己的教訓寫著
    # 「溯源／grounding 要在**程式結構上保證**，不靠模型自律」，而清理的結果**會落庫**：
    # 改壞了原文就沒有原文了（原文為真相，history/082）。
    from ..text.protect import mask, placeholder, restore
    masked, segments = mask(text)
    try:
        out = backend.reply([{"role": "system", "content": _CLEAN},
                             {"role": "user", "content": masked}])
    except Exception:  # noqa: BLE001 - 清理失敗不擋收進
        return text
    out = (out or "").strip()
    if not out:
        return text
    # 模型可能弄丟佔位符。清理是**刪雜訊**，本來就會少東西，所以不能要求全數存在；
    # 但**留下來的必須還原得回去**，而任何被吃掉的佔位符代表那段承重內容不見了 → 退回原文。
    missing = [i for i in range(len(segments)) if placeholder(i) not in out]
    if missing and len(missing) == len(segments) and segments:
        return text                      # 全部不見＝模型沒照規則走，別採用
    return restore(out, segments)
