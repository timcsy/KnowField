"""資料實體（對應 data-model.md）。以 dataclass 表達，儲存映射見 store/。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# 來源類型與取得方式（列舉為字串，驗證於建構時）
SOURCE_TYPES = ("paper", "news", "blog")
ACCESS_METHODS = (
    "arxiv_api",
    "hf_papers",
    "semantic_scholar",
    "rss",
    "email_ingest",
)


@dataclass
class Source:
    """一個可取得條目的出處。"""

    id: str
    name: str
    type: str
    access_method: str
    endpoint: str
    enabled: bool = True
    last_fetch_at: datetime | None = None
    last_status: str = ""

    def __post_init__(self) -> None:
        if self.type not in SOURCE_TYPES:
            raise ValueError(f"未知的來源類型：{self.type}")
        if self.access_method not in ACCESS_METHODS:
            raise ValueError(f"未知的取得方式：{self.access_method}")
        if not self.endpoint:
            raise ValueError("來源 endpoint 不得為空")


@dataclass
class Item:
    """一則新聞或論文。"""

    source_id: str
    external_id: str
    title: str
    url: str
    abstract: str = ""
    published_at: datetime | None = None
    lang: str = "en"
    id: int | None = None
    cluster_id: int | None = None
    fetched_at: datetime | None = None
    content_hash: str = ""

    def has_source_link(self) -> bool:
        """FR-006：進入匯整的條目必須能直達原文。"""
        return bool(self.url and self.url.strip())


@dataclass
class EventCluster:
    """一組被判定為同一則/同一事件的條目，去重單位。"""

    canonical_item_id: int
    member_item_ids: list[int] = field(default_factory=list)
    signature: str = ""
    id: int | None = None


@dataclass
class Summary:
    """封頂摘要（一句定位＋一句為何值得看）。"""

    item_id: int
    positioning: str
    why_worth: str
    generated_at: datetime | None = None

    def text(self) -> str:
        return f"{self.positioning} {self.why_worth}".strip()


@dataclass
class InterestProfile:
    """使用者興趣畫像。明講清單優先於學習權重（憲章原則 VI）。"""

    explicit_topics: list[str] = field(default_factory=list)
    learned_weights: dict[str, float] = field(default_factory=dict)
    id: int = 1
    updated_at: datetime | None = None


@dataclass
class DigestEntry:
    item: Item
    rank: int
    relevance_score: float
    summary: Summary | None = None
    matched_topic: str = ""


@dataclass
class Digest:
    """某日產出的去重且排序後匯整。"""

    date: str
    entries: list[DigestEntry] = field(default_factory=list)
    truncated_count: int = 0
    missing_sources: list[str] = field(default_factory=list)
    id: int | None = None

    @property
    def is_empty(self) -> bool:
        return len(self.entries) == 0


@dataclass
class BehaviorSignal:
    """使用者對條目的行為（US3）。"""

    item_id: int
    action: str  # "clicked" | "skipped"
    at: datetime | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.action not in ("clicked", "skipped"):
            raise ValueError(f"未知的行為：{self.action}")
