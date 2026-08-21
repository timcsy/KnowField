"""來源語言判定（spec 038，FR-009）。

只需要回答一個問題：**這篇要不要提供「翻成繁中」的動作**。
用 CJK 字元佔比，純函式、零相依——為一個閾值判斷引入語言偵測套件違反憲章 IV。

閾值來自探針掃語料的實測：三篇英文來源 CJK 佔比皆 0.0%，中文來源 > 15%，
中間是空的，所以 3% 這個切點很寬鬆——它容得下「英文文章引用幾個中文術語」。
"""
from __future__ import annotations

import re

_CJK = re.compile(r"[一-鿿]")
_THRESHOLD = 0.03


def cjk_ratio(text: str) -> float:
    """CJK 字元佔非空白字元的比例。空內容回 0.0。"""
    body = "".join(text.split())
    if not body:
        return 0.0
    return len(_CJK.findall(body)) / len(body)


def is_english(text: str) -> bool:
    """這份內容是否為英文來源（值得提供翻譯動作）。

    空內容回 False——沒有可翻的東西就不該出現那個按鈕。
    """
    if not text.strip():
        return False
    return cjk_ratio(text) < _THRESHOLD
