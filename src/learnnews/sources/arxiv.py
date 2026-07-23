"""arXiv adapter：解析 arXiv API 的 Atom 回應。"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

from ..models import Item
from .base import SourceAdapter, SourceUnavailable

_ATOM = "{http://www.w3.org/2005/Atom}"


class ArxivAdapter(SourceAdapter):
    name = "arxiv"
    type = "paper"

    def fetch(self, since: datetime) -> list[Item]:
        raw = self._fetch_raw(since)
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            raise SourceUnavailable(f"arXiv 回應無法解析：{e}") from e

        items: list[Item] = []
        for entry in root.findall(f"{_ATOM}entry"):
            arxiv_id = (entry.findtext(f"{_ATOM}id") or "").strip()
            title = (entry.findtext(f"{_ATOM}title") or "").strip()
            summary = (entry.findtext(f"{_ATOM}summary") or "").strip()
            url = arxiv_id  # arXiv id 即為直達原文 URL
            for link in entry.findall(f"{_ATOM}link"):
                if link.get("rel") == "alternate":
                    url = link.get("href", url)
            published = _parse_dt(entry.findtext(f"{_ATOM}published"))
            item = Item(
                source_id=self.source_id,
                external_id=arxiv_id,
                title=title,
                abstract=summary,
                url=url,
                published_at=published,
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
