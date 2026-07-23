"""RSS/Atom adapter：承載精選新聞源，也用於 email-ingestion 產生的 Atom feed。
以 stdlib xml.etree 解析 RSS 2.0 與 Atom。"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

from ..models import Item
from .base import SourceAdapter, SourceUnavailable

_ATOM = "{http://www.w3.org/2005/Atom}"


class RssAdapter(SourceAdapter):
    name = "rss"
    type = "news"

    def fetch(self, since: datetime) -> list[Item]:
        raw = self._fetch_raw(since)
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            raise SourceUnavailable(f"RSS/Atom 回應無法解析：{e}") from e

        # RSS 2.0：channel/item；Atom：feed/entry
        channel = root.find("channel")
        if channel is not None:
            return [self._from_rss(el) for el in channel.findall("item")]
        return [self._from_atom(el) for el in root.findall(f"{_ATOM}entry")]

    def _from_rss(self, el: ET.Element) -> Item:
        title = (el.findtext("title") or "").strip()
        link = (el.findtext("link") or "").strip()
        desc = (el.findtext("description") or "").strip()
        guid = (el.findtext("guid") or link).strip()
        item = Item(
            source_id=self.source_id, external_id=guid, title=title,
            abstract=desc, url=link, published_at=_rss_dt(el.findtext("pubDate")),
            lang="en",
        )
        return self._finalize(item)

    def _from_atom(self, el: ET.Element) -> Item:
        title = (el.findtext(f"{_ATOM}title") or "").strip()
        summary = (el.findtext(f"{_ATOM}summary") or "").strip()
        guid = (el.findtext(f"{_ATOM}id") or "").strip()
        link = guid
        for lk in el.findall(f"{_ATOM}link"):
            if lk.get("rel") in (None, "alternate"):
                link = lk.get("href", link)
        item = Item(
            source_id=self.source_id, external_id=guid, title=title,
            abstract=summary, url=link,
            published_at=_atom_dt(el.findtext(f"{_ATOM}updated")), lang="en",
        )
        return self._finalize(item)


def _rss_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _atom_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
