"""RAG 型別（data-model.md）。純資料，無外部相依。"""

from __future__ import annotations

from dataclasses import dataclass, field

Vector = list[float]


@dataclass
class CorpusEntry:
    """一則已落庫匯整條目——檢索與溯源的最小單位。"""

    entry_id: int          # → digest_entries.id
    title: str             # 原文標題
    url: str               # 原文連結（溯源）
    headline: str = ""     # 整理過標題
    body: str = ""         # 消化散文
    digest_date: str = ""  # 所屬匯整日期
    source_class: str = "ordinary"  # 'ordinary' | 'explainer'（種子品質類，spec 006）

    def embed_text(self) -> str:
        """嵌入用文字：整理標題＋消化散文（皆空則退回原標題）。"""
        parts = [p for p in (self.headline, self.body) if p and p.strip()]
        return "\n".join(parts) if parts else self.title


@dataclass
class Source:
    """答案引用的來源（對應答案裡的 [n]）。"""

    n: int
    title: str
    url: str


@dataclass
class RagAnswer:
    """問答回傳：答案文字＋程式端生成的來源清單＋查無旗標。"""

    text: str = ""
    sources: list[Source] = field(default_factory=list)
    no_material: bool = False


@dataclass
class Scope:
    """檢索範圍。today=False＝累積全部；True＝最近一份匯整。"""

    today: bool = False
