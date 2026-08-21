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
_INLINE_MATH = re.compile(r"\$[^$\n]+?\$")


def _snap_out_of_math(text: str, lo: int, pos: int) -> int:
    """把切點 pos 移出行內 $..$ 中間（退到該數學之前，整條數學留給下一塊）——否則切半＋stitch
    的 \\n\\n 會插進行內數學、前端 $ 配對連鎖崩壞。數學本身比 target 還長→只好原位硬切。"""
    for m in _INLINE_MATH.finditer(text):
        if m.start() >= pos:
            break
        if m.start() < pos < m.end():
            return m.start() if m.start() > lo else pos
    return pos


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


def dedupe_for_translate(chunks: list[str], max_overlap: int = 120
                         ) -> tuple[list[str], list[str]]:
    """把塊間重疊裁掉，回 `(pieces, seps)`；`pieces[0]+seps[0]+pieces[1]+…` 逐字等於
    `stitch_chunks(chunks)`。

    **為什麼需要它**（spec 038）：`stitch_chunks` 靠**精確字串比對**去重疊，那對原文成立；
    但每塊若被**獨立翻譯**，同一段重疊文字在前後塊會翻成不同的中文，比對就失敗，
    兩份都會留下——接縫出現「條件式 Generat … 條件式生成」這種殘影。
    ⇒ 重疊要在**翻譯前**裁掉，翻完照原本的分隔接回。

    與 `stitch_chunks` 共用同一套判斷（同樣的 `max_overlap`、同樣的 `\n\n` 後備），
    兩者必須一起改，否則重組會對不上。
    """
    parts = [c for c in chunks if c and c.strip()]
    if not parts:
        return [], []
    pieces, seps = [parts[0]], []
    tail = parts[0]
    for ch in parts[1:]:
        k = min(len(tail), len(ch), max_overlap)
        ov = 0
        for j in range(k, 0, -1):
            if tail[-j:] == ch[:j]:
                ov = j
                break
        if ov:
            pieces.append(ch[ov:])
            seps.append("")
        else:
            pieces.append(ch)
            seps.append("\n\n")
        tail = ch
    return pieces, seps


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
            end = min(start + target, len(text))
            if end < len(text):
                end = _snap_out_of_math(text, start, end)   # 別切在行內數學中間
                if end <= start:                            # 數學比 target 長→硬切避免死迴圈
                    end = min(start + target, len(text))
            cur = text[start:end]
            if end >= len(text):
                break                                       # 最後一片留在 cur（迴圈外 push）
            push()
            nxt = _snap_out_of_math(text, start, max(start + 1, end - overlap))  # 重疊起點也不切數學
            start = nxt if nxt > start else end
    push()
    return chunks
