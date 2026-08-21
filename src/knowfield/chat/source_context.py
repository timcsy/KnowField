"""帶入來源的選段（spec 042）。

⚠️ **為什麼不是 `text[:CAP]`**：spec 041 對文章就是那樣硬切的，而來源比文章大一個量級
（實測 20k–38k 字），硬切會讓後半**無聲消失**——使用者看不到、模型也不知道自己少看了什麼，
於是它會用「這篇沒提到」的語氣回答一件其實有提到的事。那是沉默失敗（FR-005 明文禁止）。

取而代之：**開頭（保住「整體在講什麼」）＋ 份內檢索命中的段落 ＋ 明講節錄了多少**。
切點一律落在**原始塊的邊界**上——寧可整段溢出一點，也不要半句。

純函式：檢索名次由呼叫端算好傳進來，所以這裡零外呼、好測。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceContext:
    body: str
    total_units: int
    shown_units: int
    excerpted: bool


_ELLIPSIS = "（此處略過與問題較不相關的段落）"


def select_source_context(chunks: list[str], ranked_idx: list[int],
                          cap: int, head_chars: int) -> SourceContext:
    """挑出要進脈絡的段落。

    `chunks`＝來源的原始塊（依序）。`ranked_idx`＝份內檢索的相關度名次（塊索引，最相關在前）。
    `cap`＝body 的字數預算；`head_chars`＝保底要留給開頭的字數。

    未超過 `cap` → 全文。超過 → 開頭若干塊 ＋ 依名次補進最相關的塊，依原順序輸出。
    """
    total = len(chunks)
    if total == 0:
        return SourceContext("", 0, 0, False)

    joined = "\n\n".join(chunks)
    if len(joined) <= cap:
        return SourceContext(joined, total, total, False)

    picked: set[int] = set()
    used = 0
    # ① 開頭一定進——沒有它就答不出「這篇整體在講什麼」。
    #    ⚠️ 即使第一塊自己就超過 head_chars 也整塊進：切半才是要避免的那件事。
    for i, c in enumerate(chunks):
        if used and used + len(c) > head_chars:
            break
        picked.add(i)
        used += len(c) + 2
    # ② 再依份內檢索名次補，直到預算用完。整塊為單位。
    for i in ranked_idx:
        if i in picked or not (0 <= i < total):
            continue
        if used + len(chunks[i]) > cap and picked:
            continue
        picked.add(i)
        used += len(chunks[i]) + 2

    # 依原順序輸出；跳號的地方明講略過了，模型才不會把沒看到的當作不存在。
    parts: list[str] = []
    prev = -1
    for i in sorted(picked):
        if prev >= 0 and i != prev + 1:
            parts.append(_ELLIPSIS)
        parts.append(chunks[i])
        prev = i
    if prev < total - 1:
        parts.append(_ELLIPSIS)
    return SourceContext("\n\n".join(parts), total, len(picked), True)
