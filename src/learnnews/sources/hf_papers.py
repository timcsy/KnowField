"""Hugging Face Daily Papers adapter：解析 HF papers 的 JSON 回應。"""

from __future__ import annotations

import json
from datetime import datetime

from ..models import Item
from .base import SourceAdapter, SourceUnavailable


class HFPapersAdapter(SourceAdapter):
    name = "hf_papers"
    type = "paper"

    def fetch(self, since: datetime) -> list[Item]:
        raw = self._fetch_raw(since)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SourceUnavailable(f"HF Papers 回應無法解析：{e}") from e

        items: list[Item] = []
        for row in data:
            paper = row.get("paper", row)
            pid = str(paper.get("id", "")).strip()
            title = (paper.get("title") or "").strip()
            summary = (paper.get("summary") or paper.get("abstract") or "").strip()
            url = paper.get("url") or (
                f"https://huggingface.co/papers/{pid}" if pid else ""
            )
            item = Item(
                source_id=self.source_id,
                external_id=pid,
                title=title,
                abstract=summary,
                url=url,
                published_at=_parse_dt(paper.get("publishedAt")),
                lang="en",
            )
            items.append(self._finalize(item))
        return items


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
