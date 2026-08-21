"""承重片段的佔位保護（spec 037，FR-006）。

**為什麼存在**：research.md 實測，未保護的 s2twp 轉換會

    def 处理(内存):        → def 處理(記憶體):      程式碼識別字被改
    http://a.cn/发展/…     → …/發展/…              URL 404
    pic1.zhimg.com/发展.jpg → …發展.jpg             破圖
    $x_{发}$               → $x_{發}$              數學下標被改

六個危險案例全中，所以保護不是防禦性加碼，是這個功能的必要條件
（同型前例：`ingest/convert.py` 的 OCR 圖片內嵌、commit 9c3352e 的中文粗體佔位）。

**抽取順序有意義**：塊級先於行內。反過來會把圍欄內部的行內語法先抽走、破壞配對。
"""
from __future__ import annotations

import re

# 佔位符：純 ASCII（s2twp 不會轉換）＋極不可能出現在原文的形狀。
# 前後留 \x00 以外的可見字元，避免與相鄰文字黏成一個「詞」而影響詞彙層轉換。
_PH_PREFIX = "@@KFPROTECT"
_PH_SUFFIX = "@@"


def placeholder(index: int) -> str:
    """第 index 個承重片段的佔位符。純 ASCII，轉換器不會動它。"""
    return f"{_PH_PREFIX}{index}{_PH_SUFFIX}"


_PH_RE = re.compile(rf"{_PH_PREFIX}(\d+){_PH_SUFFIX}")

# 順序即優先權：越前面越先抽。塊級 → 行內。
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"```.*?```", re.S),          # 圍欄程式碼（反引號）
    re.compile(r"~~~.*?~~~", re.S),          # 圍欄程式碼（波浪號）
    re.compile(r"\$\$.*?\$\$", re.S),        # 數學區塊
    re.compile(r"\\\[.*?\\\]", re.S),        # 數學區塊（LaTeX 括號式）
    re.compile(r"!\[[^\]]*\]\([^)]*\)"),     # 圖片：整段抽（含 alt，見 data-model.md 第 3 條）
    re.compile(r"(?<=\]) *\([^)]*\)"),       # 連結的 (url)：只抽網址，顯示文字留著要轉（第 4 條）
    re.compile(r"`[^`\n]+`"),                # 行內程式碼
    re.compile(r"\$[^$\n]+\$"),              # 行內數學
    re.compile(r"\\\([^\n]*?\\\)"),          # 行內數學（LaTeX 括號式）
    re.compile(r"https?://[^\s)\]<>]+"),     # 裸 URL
]


def mask(text: str) -> tuple[str, list[str]]:
    """把承重片段換成佔位符。回傳 (masked, segments)。

    不變式：``restore(*mask(t)) == t`` 對任意輸入成立。
    """
    segments: list[str] = []

    def _take(m: re.Match[str]) -> str:
        segments.append(m.group(0))
        return placeholder(len(segments) - 1)

    masked = text
    for pat in _PATTERNS:
        masked = pat.sub(_take, masked)
    return masked, segments


def restore(masked: str, segments: list[str]) -> str:
    """把佔位符換回原本的承重片段。

    由外而內反覆替換：先抽的片段可能內含後抽的佔位符（例如圍欄內的行內語法
    在圍欄被抽走後不會再被掃到，但保險起見仍迴圈到收斂）。
    """
    out = masked
    for _ in range(len(segments) + 1):
        new = _PH_RE.sub(lambda m: segments[int(m.group(1))], out)
        if new == out:
            break
        out = new
    return out
