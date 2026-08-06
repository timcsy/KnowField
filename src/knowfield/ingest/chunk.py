"""切塊純函式（spec 030）：把 markdown 切成可檢索單元。

零相依、純函式、離線可測。規則（見 research R3）：
- **原子塊不切**：fenced code（```）、`$$` 數學塊、markdown 表格（連續 `|` 列）整塊落在單一 chunk。
- **章節優先切點**：`^#{1,6} ` 標題處起新 chunk（Mistral 標題階層不穩，但「有標題就切」可靠）。
- **中文按字元數切**：章節內 prose 按字元切＋重疊（不依賴空白分詞，中文無空格）。
- 短內容→一塊；空→[]。
「查不到」root cause 多在切塊（GeneralAffairs f016）；公式/表格切半會壞檢索。
"""

from __future__ import annotations

import re

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def _segment(md: str) -> list[dict]:
    """把 md 切成 segment 序列：{text, atomic, heading}。atomic＝不可再切的整塊。"""
    lines = md.split("\n")
    segs: list[dict] = []
    prose: list[str] = []
    i, n = 0, len(lines)

    def flush_prose():
        if prose:
            txt = "\n".join(prose).strip("\n")
            if txt.strip():
                segs.append({"text": txt, "atomic": False, "heading": False})
            prose.clear()

    while i < n:
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):                         # fenced code
            flush_prose()
            buf = [line]
            i += 1
            while i < n:
                buf.append(lines[i])
                if lines[i].strip().startswith("```"):
                    i += 1
                    break
                i += 1
            segs.append({"text": "\n".join(buf), "atomic": True, "heading": False})
            continue
        if s.startswith("$$"):                          # $$ 數學塊（單行或多行）
            flush_prose()
            if len(s) > 2 and s.endswith("$$"):
                segs.append({"text": line, "atomic": True, "heading": False})
                i += 1
                continue
            buf = [line]
            i += 1
            while i < n:
                buf.append(lines[i])
                if lines[i].strip().endswith("$$"):
                    i += 1
                    break
                i += 1
            segs.append({"text": "\n".join(buf), "atomic": True, "heading": False})
            continue
        if _TABLE_ROW.match(line):                      # markdown 表格
            flush_prose()
            buf = []
            while i < n and _TABLE_ROW.match(lines[i]):
                buf.append(lines[i])
                i += 1
            segs.append({"text": "\n".join(buf), "atomic": True, "heading": False})
            continue
        if _HEADING.match(line):                        # 標題＝切點
            flush_prose()
            segs.append({"text": line, "atomic": False, "heading": True})
            i += 1
            continue
        prose.append(line)
        i += 1
    flush_prose()
    return segs


def stitch_chunks(chunks: list[str], max_overlap: int = 120) -> str:
    """把一來源的塊依序拼回、去除塊間重疊（spec 031 詳情頁看原文）。純函式。"""
    parts = [c for c in chunks if c and c.strip()]
    if not parts:
        return ""
    out = parts[0]
    for ch in parts[1:]:
        k = min(len(out), len(ch), max_overlap)
        ov = 0
        for j in range(k, 0, -1):
            if out[-j:] == ch[:j]:
                ov = j
                break
        out = out + ch[ov:] if ov else out + "\n\n" + ch
    return out


def chunk_markdown(md: str, target: int = 400, overlap: int = 40) -> list[str]:
    """把 markdown 切成 chunk 清單。target＝目標字元數、overlap＝prose 跨塊重疊字元數。"""
    md = (md or "").strip()
    if not md:
        return []
    segs = _segment(md)
    chunks: list[str] = []
    cur = ""

    def push():
        nonlocal cur
        if cur.strip():
            chunks.append(cur.strip())
        cur = ""

    def add(text):
        nonlocal cur
        cur = text if not cur else cur + "\n\n" + text

    for seg in segs:
        text = seg["text"]
        if not text.strip():
            continue
        if seg["heading"] and cur.strip():              # 標題→起新塊
            push()
        if seg["atomic"]:                               # 原子塊：不切，自成/併塊
            if cur and len(cur) + len(text) > target:
                push()
            add(text)
            if len(cur) >= target:
                push()
            continue
        if len(cur) + len(text) <= target:              # prose 塞得下→併入
            add(text)
            continue
        if cur.strip():                                 # 塞不下→先收掉現有塊
            push()
        start = 0                                       # 按字元切這段 prose（帶重疊）
        while start < len(text):
            cur = text[start:start + target]
            if start + target < len(text):
                push()
                start += max(1, target - overlap)
            else:
                start += target                         # 最後一片留在 cur
    push()
    return chunks
