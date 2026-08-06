"""可插拔 web 搜尋後端（spec 009）。

離線預設 `StubWebSearch`（回固定假結果、可測）；真實 `ApiWebSearch` 以 stdlib urllib POST
到設定的搜尋 API（Tavily 形狀寬鬆解析），**不加 pip 相依**。失敗拋 `SourceUnavailable`（繁中）。
搜尋結果 `SearchResult` 為短暫物件——不落庫，只有使用者「收進」才經 ingest 成種子（原則 5）。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from ..sources.base import SourceUnavailable


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class WebSearch(Protocol):
    def search(self, query: str, *, news: bool = False,
               time_range: str | None = None) -> list[SearchResult]: ...


class StubWebSearch:
    """離線假搜尋：回固定結果（零外部呼叫，供測試/離線）。news/time_range 接受但忽略。"""

    def search(self, query: str, *, news: bool = False,
               time_range: str | None = None) -> list[SearchResult]:
        q = (query or "").strip()
        return [
            SearchResult(f"（離線示意）關於「{q}」的結果 1", "https://example.com/1",
                         "離線 stub 結果——設定搜尋 API 金鑰即可啟用真實開放網路搜尋。"),
            SearchResult(f"（離線示意）關於「{q}」的結果 2", "https://example.com/2",
                         "離線 stub 結果。"),
        ]


def _http_post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 - 統一轉成友善的來源不可用
        raise SourceUnavailable(f"搜尋服務失敗：{e}") from e


class ApiWebSearch:
    """Tavily 相容搜尋（POST，`api_key` 放 body）。`poster(url, payload)` 可注入供測試。

    預設對 Tavily（`https://api.tavily.com/search`，回 `{results:[{title,url,content}]}`）；
    回應解析寬鬆，換相容服務多半可直接用。
    """

    def __init__(self, api_url: str, api_key: str, max_results: int = 8,
                 poster=_http_post_json) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.max_results = max_results
        self._poster = poster

    def search(self, query: str, *, news: bool = False,
               time_range: str | None = None) -> list[SearchResult]:
        payload = {
            "api_key": self.api_key, "query": query,
            "max_results": self.max_results, "include_answer": False,
        }
        if news:                                  # news 模式：只回近期新聞（Tavily topic/time_range）
            payload["topic"] = "news"
            if time_range:
                payload["time_range"] = time_range
        data = self._poster(self.api_url, payload)
        raw = data.get("results") or data.get("data") or data.get("items") or []
        out: list[SearchResult] = []
        for r in raw:
            url = (r.get("url") or r.get("link") or "").strip()
            if not url:
                continue
            title = (r.get("title") or r.get("name") or url).strip()
            snippet = (r.get("content") or r.get("snippet")
                       or r.get("description") or "").strip()[:300]
            out.append(SearchResult(title=title, url=url, snippet=snippet))
        return out
