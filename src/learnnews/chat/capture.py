"""收料純核心（spec 025）：內容指紋（去重識別）＋收尾缺口判準。

零相依、純函式、離線可測、缺項不崩。指紋供「同一段對話」去重；判準供「尾段未收」提醒。
"""

from __future__ import annotations

import hashlib


def conversation_fingerprint(messages: list) -> str:
    """訊息序列的穩定指紋：取每則 role＋content（忽略 sources 等易變欄）雜湊。

    同 role/content 序列 → 同指紋；順序或內容不同 → 不同。空／缺 content 不崩。
    """
    parts: list[str] = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "")
        content = str(m.get("content") or "")
        parts.append(role + "\x1f" + content)
    blob = "\x1e".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def distill_gap(total: int, last_captured: int | None,
                min_total: int, gap_threshold: int) -> tuple[int, int] | None:
    """尾段未收判準（純值）。

    回 (from, to)＝(last_captured+1, total)，當「對話夠長」（total>=min_total）
    且「自上次收以來又長出一大段」（total-last_captured>=gap_threshold）；否則 None。
    last_captured 負/None 視為 0；total<=0 → None。
    """
    if not total or total <= 0:
        return None
    lc = last_captured if isinstance(last_captured, int) and last_captured > 0 else 0
    if total >= min_total and (total - lc) >= gap_threshold:
        return (lc + 1, total)
    return None
