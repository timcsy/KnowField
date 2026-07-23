"""從原文抓代表圖（best-effort、離線）。

MVP 策略：解析材料的前文/描述 HTML 取第一張 <img>（新聞 RSS 常內嵌）。
取不到就回 None（不拋例外、不阻塞，FR-006/契約）。arXiv 論文 figure 需解析 HTML 版，
成本高，MVP 不做（回 None → 退純文字或 AI 示意）。
"""

from __future__ import annotations

import re

from ..models import Item
from ..summarize.article import Figure

_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def extract_figure(item: Item) -> Figure | None:
    """從 item.abstract（可能含 HTML）取第一張圖；取不到回 None。"""
    m = _IMG_RE.search(item.abstract or "")
    if not m:
        return None
    url = m.group(1).strip()
    if not url:
        return None
    return Figure(kind="原文", url=url, source_note=f"取自原文（{item.source_id}）")
