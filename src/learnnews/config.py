"""設定（YAGNI：以 dataclass ＋環境變數，無外部設定框架）。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    db_path: str = "learnnews.db"
    digest_limit: int = 15          # SC-007 預設上限
    relevance_threshold: float = 0.10  # 低於此相關性即濾除
    dedup_similarity: float = 0.82     # 語義去重 cosine 門檻
    summary_model: str = "claude-haiku-4-5"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            db_path=os.environ.get("LEARNNEWS_DB", "learnnews.db"),
            digest_limit=int(os.environ.get("LEARNNEWS_LIMIT", "15")),
        )
