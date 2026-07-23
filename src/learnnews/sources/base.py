"""來源 adapter 基底介面（contracts/source-adapter.md）。

契約：`fetch()` 回傳的每個 Item MUST 有非空 url（FR-006）；取得失敗 MUST 明確
拋出 SourceUnavailable（附繁中原因），不得靜默或回傳半成品（原則 V）。
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Callable

from ..models import Item


class SourceUnavailable(Exception):
    """來源當日不可取得（逾時、失效、達用量上限、解析錯誤）。"""


def canonical_url(url: str) -> str:
    """正規化 URL 供去重（去除 scheme、www、尾斜線、查詢字串）。"""
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("?")[0].split("#")[0]
    return u.rstrip("/")


def normalize_title(title: str) -> str:
    return re.sub(r"[\s\W_]+", "", (title or "").lower())


def content_hash(external_id: str, title: str, url: str) -> str:
    """精確去重鍵：優先用 external_id，否則用正規化標題＋canonical URL。"""
    key = external_id.strip().lower() if external_id else (
        normalize_title(title) + "|" + canonical_url(url)
    )
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


class SourceAdapter:
    """所有來源 adapter 的基底。子類實作 `fetch`。

    `fetch_raw` 為可注入的取得原始資料函式（測試以 fixtures 注入，
    生產以 HTTP 取得），讓解析邏輯離線可測。
    """

    name: str = "base"
    type: str = "paper"

    def __init__(self, source_id: str, fetch_raw: Callable[[datetime], str]) -> None:
        self.source_id = source_id
        self._fetch_raw = fetch_raw

    def fetch(self, since: datetime) -> list[Item]:  # pragma: no cover - 抽象
        raise NotImplementedError

    def _finalize(self, item: Item) -> Item:
        """補上 content_hash 並確保 url 非空（否則視為契約違反）。"""
        if not item.has_source_link():
            raise SourceUnavailable(
                f"來源 {self.name} 回傳無原文連結的條目：{item.title!r}"
            )
        item.content_hash = content_hash(item.external_id, item.title, item.url)
        return item
