"""測試共用：假 adapter 與樣本條目。"""

from __future__ import annotations

from datetime import datetime

from knowfield.models import Item
from knowfield.sources.base import SourceAdapter, SourceUnavailable, content_hash


class FakeAdapter(SourceAdapter):
    """回傳預先給定的條目；或設定為失敗以驗證缺漏處理。"""

    def __init__(self, name: str, items: list[Item], fail: bool = False) -> None:
        super().__init__(source_id=name, fetch_raw=lambda since: "")
        self.name = name
        self._items = items
        self._fail = fail

    def fetch(self, since: datetime) -> list[Item]:
        if self._fail:
            raise SourceUnavailable(f"{self.name} 模擬失敗")
        out = []
        for it in self._items:
            it.content_hash = content_hash(it.external_id, it.title, it.url)
            out.append(it)
        return out


def make_item(title, external_id="", url="https://example.org/x", abstract="",
              source_id="s", published=None) -> Item:
    return Item(
        source_id=source_id,
        external_id=external_id,
        title=title,
        abstract=abstract,
        url=url,
        published_at=published or datetime(2026, 7, 23),
        content_hash=content_hash(external_id, title, url),
    )
