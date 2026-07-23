"""拉模式資料型別（data-model.md）。Item／Summary 複用推模式的 models。"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Item, Summary


@dataclass
class TopicQuery:
    topic: str
    limit: int = 30
    with_summary: bool = True


@dataclass
class PullEntry:
    item: Item
    rank: int
    relevance_score: float
    summary: Summary | None = None  # --raw 時為 None


@dataclass
class PullResult:
    topic: str
    entries: list[PullEntry] = field(default_factory=list)
    truncated_count: int = 0
    missing_sources: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.entries) == 0
