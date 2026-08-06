"""Semantic Scholar adapter：解析 Academic Graph API 的 JSON，含指數退避
（research.md R1：官方已收緊速率，須退避）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Callable

from ..models import Item
from .base import SourceAdapter, SourceUnavailable


class RateLimited(Exception):
    """來源回報速率限制，應退避重試。"""


def with_backoff(
    fn: Callable[[datetime], str],
    since: datetime,
    max_attempts: int = 4,
    sleep: Callable[[float], None] | None = None,
) -> str:
    """對 RateLimited 做指數退避重試。sleep 可注入（測試用 no-op）。"""
    sleep = sleep or (lambda _s: None)
    delay = 0.5
    last: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn(since)
        except RateLimited as e:
            last = e
            sleep(delay)
            delay *= 2
    raise SourceUnavailable(
        f"Semantic Scholar 多次退避後仍受速率限制：{last}"
    )


class SemanticScholarAdapter(SourceAdapter):
    name = "semantic_scholar"
    type = "paper"

    def __init__(self, source_id, fetch_raw, sleep=None) -> None:
        super().__init__(source_id, fetch_raw)
        self._sleep = sleep

    def fetch(self, since: datetime) -> list[Item]:
        raw = with_backoff(self._fetch_raw, since, sleep=self._sleep)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SourceUnavailable(f"Semantic Scholar 回應無法解析：{e}") from e

        items: list[Item] = []
        for row in payload.get("data", []):
            ext = row.get("externalIds", {}) or {}
            external_id = ext.get("ArXiv") or ext.get("DOI") or row.get("paperId", "")
            url = row.get("url") or ""
            item = Item(
                source_id=self.source_id,
                external_id=str(external_id),
                title=(row.get("title") or "").strip(),
                abstract=(row.get("abstract") or "").strip(),
                url=url,
                published_at=_parse_dt(row.get("publicationDate")),
                lang="en",
            )
            items.append(self._finalize(item))
        return items


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
