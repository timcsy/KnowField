"""去重精確層（FR-002）：以 content_hash（external_id / 正規化標題＋canonical URL）
把明確重複者分到同一群。多數跨源重複是同一 ID 的轉貼，此層低成本解決大宗。"""

from __future__ import annotations

from ..models import Item
from ..sources.base import content_hash


def group_exact(items: list[Item]) -> list[list[Item]]:
    """回傳分群：每個子清單為判定相同的條目集合。"""
    buckets: dict[str, list[Item]] = {}
    for item in items:
        key = item.content_hash or content_hash(
            item.external_id, item.title, item.url
        )
        item.content_hash = key
        buckets.setdefault(key, []).append(item)
    return list(buckets.values())
