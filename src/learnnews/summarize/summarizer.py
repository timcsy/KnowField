"""封頂摘要器：呼叫後端並施加程式端守衛（FR-004/005、SC-004）。

守衛不依賴模型自律：
- 長度封頂：定位與為何值得看各取第一句，合計 ≤ 2 句。
- 不代勞：後端只被要求給定位/值得看；此處再截斷確保不溢出成分析。
"""

from __future__ import annotations

import re
from datetime import datetime

from ..models import Item, Summary
from .llm import StubSummarizer, Summarizer

_SENT_SPLIT = re.compile(r"[。！？!?\.]+")


def first_sentence(text: str) -> str:
    text = (text or "").strip()
    parts = [p for p in _SENT_SPLIT.split(text) if p.strip()]
    return parts[0].strip() if parts else text


def count_sentences(text: str) -> int:
    return len([p for p in _SENT_SPLIT.split(text or "") if p.strip()])


class SummaryBuilder:
    def __init__(self, backend: Summarizer | None = None) -> None:
        self.backend = backend or StubSummarizer()

    def build(self, item: Item, matched_topic: str) -> Summary:
        positioning, why = self.backend.summarize(
            item.title, item.abstract, matched_topic
        )
        # 程式端守衛：各取第一句，確保封頂 ≤ 2 句（SC-004）
        positioning = first_sentence(positioning)
        why = first_sentence(why)
        summary = Summary(
            item_id=item.id or 0,
            positioning=positioning,
            why_worth=why,
            generated_at=datetime(2026, 7, 23),
        )
        # 硬性不變式：整體不得超過兩句
        assert count_sentences(summary.text()) <= 2
        return summary
