"""收料純核心（spec 025）：內容指紋（去重識別）＋收尾缺口判準。

零相依、純函式、離線可測、缺項不崩。指紋供「同一段對話」去重；判準供「尾段未收」提醒。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


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


@dataclass
class DedupePlan:
    """既有重複對話清理計畫（spec 026）：純值、不落庫。"""
    delete_ids: list = field(default_factory=list)   # 待刪的多餘份 ids
    repoint: dict = field(default_factory=dict)      # {why_node_id: 留存 conversation_id}
    n_groups: int = 0                                # 有重複的組數
    n_extra: int = 0                                 # 多餘份數（＝len(delete_ids)）
    n_roots: int = 0                                 # 將重指的根因數（＝len(repoint)）


def plan_dedupe(convos: list, provenance: dict) -> DedupePlan:
    """算既有重複對話的清理計畫（純函式，非破壞）。

    依內容指紋分組；每組（>1 份）留 id 最大者（最新），其餘列入待刪；指向待刪份的根因
    連結（provenance: {wid: cid}）重指到留存份。只併同指紋、異指紋不入計畫。空/無重複→空計畫。
    """
    groups: dict = {}
    for c in convos or []:
        if not isinstance(c, dict) or "id" not in c:
            continue
        fp = conversation_fingerprint(c.get("messages") or [])
        groups.setdefault(fp, []).append(c["id"])

    delete_ids: list = []
    survivor_of: dict = {}     # {loser_cid: survivor_cid}
    n_groups = 0
    for ids in groups.values():
        if len(ids) < 2:
            continue
        n_groups += 1
        survivor = max(ids)
        for cid in ids:
            if cid != survivor:
                delete_ids.append(cid)
                survivor_of[cid] = survivor

    repoint: dict = {}
    for wid, cid in (provenance or {}).items():
        if cid in survivor_of:
            repoint[wid] = survivor_of[cid]

    delete_ids.sort()
    return DedupePlan(delete_ids=delete_ids, repoint=repoint, n_groups=n_groups,
                      n_extra=len(delete_ids), n_roots=len(repoint))


def title_material(messages: list, head_chars: int = 600, tail_chars: int = 1600) -> str:
    """為標題取材（spec 027）：首段＋尾段並取（尾為主），讓標題反映**落點**、不只開頭。

    修正舊 title 只餵 convo[:2000]（只看開頭）的成因。空→空字串、缺 content 不崩。
    """
    parts: list[str] = []
    for m in messages or []:
        if isinstance(m, dict):
            parts.append(f"{m.get('role')}：{m.get('content') or ''}")
    convo = "\n".join(parts)
    if not convo:
        return ""
    if len(convo) <= head_chars + tail_chars:
        return convo
    return convo[:head_chars] + "\n…（中略）…\n" + convo[-tail_chars:]


def normalize_chapters(raw: list, n_messages: int) -> list:
    """把切分器給的粗章節（可能越界/亂序/重疊）正規化（spec 027，純函式）。

    以各章 start 為邊界：clamp 到 [1,n]、排序去重、首章補到 1，章 i 覆蓋 [start_i, start_{i+1}-1]、
    末章到 n → 保證**涵蓋 [1,n] 且不重疊**。空/壞且 n≥1→整段一章；n≤0→[]。
    """
    if not n_messages or n_messages <= 0:
        return []
    items: list = []
    for c in raw or []:
        if not isinstance(c, dict):
            continue
        try:
            s = int(c.get("start"))
        except (TypeError, ValueError):
            continue
        s = max(1, min(s, n_messages))
        items.append({"start": s, "title": (c.get("title") or "").strip(),
                      "summary": (c.get("summary") or "").strip()})
    if not items:
        return [{"title": "整段", "start": 1, "end": n_messages, "summary": ""}]
    items.sort(key=lambda x: x["start"])
    dedup: list = []
    seen: set = set()
    for it in items:
        if it["start"] in seen:
            continue
        seen.add(it["start"])
        dedup.append(it)
    dedup[0]["start"] = 1     # 首章補到開頭，確保涵蓋
    out: list = []
    for i, it in enumerate(dedup):
        end = dedup[i + 1]["start"] - 1 if i + 1 < len(dedup) else n_messages
        out.append({"title": it["title"] or f"第 {i + 1} 章", "start": it["start"],
                    "end": end, "summary": it["summary"]})
    return out
