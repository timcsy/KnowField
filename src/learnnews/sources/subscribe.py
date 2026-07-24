"""來源訂閱：從一個網址探測 RSS/Atom feed、驗證有料、建成 Source（spec 008）。

`http_get` 可注入（離線可測，教訓 1）。**加前必驗證有料才落庫**（教訓 7）：死 feed 不入庫。
失敗統一拋 `SourceUnavailable`（繁中）。
"""

from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from ..models import Source
from ..seed.fetch import default_http_get
from .base import SourceUnavailable
from .rss import RssAdapter


class _FeedLinkParser(HTMLParser):
    """找 <link rel="alternate" type="application/rss+xml|atom+xml" href="…">。"""

    def __init__(self) -> None:
        super().__init__()
        self.feed_href: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag != "link" or self.feed_href:
            return
        d = {k.lower(): (v or "") for k, v in attrs}
        rel = d.get("rel", "").lower()
        typ = d.get("type", "").lower()
        if "alternate" in rel and ("rss+xml" in typ or "atom+xml" in typ) and d.get("href"):
            self.feed_href = d["href"]


def _looks_like_feed(raw: str) -> bool:
    head = raw.lstrip()[:500].lower()
    return "<rss" in head or "<feed" in head or ("<?xml" in head and "<channel" in head)


def discover_feed(url: str, http_get=default_http_get) -> str | None:
    """回 feed URL：url 本身是 feed→用它；否則抓 HTML 找 alternate link；找不到→None。"""
    raw = http_get(url)
    if _looks_like_feed(raw):
        return url
    p = _FeedLinkParser()
    try:
        p.feed(raw)
    except Exception:  # noqa: BLE001
        return None
    return urljoin(url, p.feed_href) if p.feed_href else None


def validate_feed(feed_url: str, http_get=default_http_get) -> list:
    """實測抓一次；回條目（≥1 才算有效）。復用 RssAdapter，不另寫 parser。"""
    adapter = RssAdapter("_probe", lambda since: http_get(feed_url))
    return adapter.fetch(datetime(2000, 1, 1))


def _feed_title(raw: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip()[:80] if m else ""


def _source_id(feed_url: str) -> str:
    dom = urlparse(feed_url).netloc.lower()
    dom = dom[4:] if dom.startswith("www.") else dom
    slug = re.sub(r"[^a-z0-9]+", "-", dom).strip("-")
    return f"sub-{slug or 'feed'}"


def subscribe(url: str, http_get=default_http_get) -> Source:
    """探測→驗證有料→建 Source（啟用）。失敗拋 SourceUnavailable（繁中）。"""
    url = (url or "").strip()
    if not url:
        raise SourceUnavailable("請提供網址")
    feed_url = discover_feed(url, http_get)
    if not feed_url:
        raise SourceUnavailable("找不到 RSS/Atom feed，該站可能沒提供")
    items = validate_feed(feed_url, http_get)          # 可能拋 SourceUnavailable
    if not items:
        raise SourceUnavailable("這個 feed 目前抓不到內容")
    name = _feed_title(http_get(feed_url)) or urlparse(feed_url).netloc
    return Source(id=_source_id(feed_url), name=name, type="blog",
                  access_method="rss", endpoint=feed_url, enabled=True)
