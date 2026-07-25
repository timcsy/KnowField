"""WebSearchAdapter（spec 015／階段 13）：把開放網路搜尋當成一個來源，接進每日 digest。

治痛點：固定名冊（論文骨幹＋週刊）抓不到剛紅的產品新聞（Opus 5 這種）。本 adapter 對一組
「AI 最新」查詢跑既有 `WebSearch` 後端（spec 009），把結果映成 `Item` 餵進既有 digest 管線
（去重/依興趣排序/消化）——concept 反濾泡/驚訝力：伸手到策展名冊之外。

web 進的是**當日流**（如同其他來源的匯整條目），**不是種子**；要留仍靠使用者「收進」（原則 5）。
搜尋失敗向外拋 `SourceUnavailable` → digest 攔成 missing（教訓 3）。離線用 `StubWebSearch` 可測。
"""

from __future__ import annotations

from datetime import datetime

from ..models import Item
from .base import SourceAdapter


def _norm_url(url: str) -> str:
    u = (url or "").strip().split("#", 1)[0]
    return u.rstrip("/")


class WebSearchAdapter(SourceAdapter):
    """實作 SourceAdapter.fetch，用搜尋後端而非 HTTP endpoint（故自訂 __init__）。"""

    type = "news"

    def __init__(self, source_id: str, web_search, queries: list[str]) -> None:
        self.source_id = source_id
        self.name = source_id                 # digest 缺漏標示用 adapter.name
        self.web_search = web_search
        self.queries = queries

    def fetch(self, since: datetime) -> list[Item]:
        # web 結果無可靠日期 → 不做 since 過濾（MVP，靠 digest 排序/去重把關）
        out: list[Item] = []
        seen: set[str] = set()
        for q in self.queries:
            for r in self.web_search.search(q):    # 拋 SourceUnavailable → 向外拋（digest 攔）
                key = _norm_url(r.url)
                if not key or key in seen:
                    continue
                seen.add(key)
                out.append(self._finalize(Item(
                    source_id="web", external_id="", title=r.title,
                    url=r.url, abstract=r.snippet)))
        return out
