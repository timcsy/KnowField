"""智慧搜尋（spec 010）：RAG over 搜尋結果——排序 → 抓 top-N 內文 → grounded 整理。

編排既有零件（不重寫）：`WebSearch`（spec 009）、`Embedder`＋cosine、`fetch_url`（spec 006）、
`Answerer`＋`_is_no_material`（spec 005）。全部依賴可注入 → 離線 stub 零外部呼叫可測（教訓 1）。
整理只根據抓到的內文（grounded，教訓 7）；單則抓不到退回 snippet、整理失敗仍保留結果（教訓 3）。
產物一律不落庫——只有使用者「收進」才成種子（原則 5）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..rag.service import _is_no_material
from ..rag.types import CorpusEntry, Source
from ..ranking.embeddings import cosine
from ..seed.fetch import fetch_url
from .websearch import SearchResult

_OVERVIEW_ERR = "整理暫時無法產生，以下為原始搜尋結果（仍可收進）。"


@dataclass
class SmartResult:
    """一次智慧搜尋的短暫產出（不落庫）。"""

    overview: str = ""
    sources: list[Source] = field(default_factory=list)
    no_material: bool = False
    results: list[SearchResult] = field(default_factory=list)
    overview_error: str | None = None


def _norm_url(url: str) -> str:
    """去重用網址正規化：去尾斜線與 #fragment（query string 保留）。"""
    u = (url or "").strip()
    u = u.split("#", 1)[0]
    return u.rstrip("/")


class SmartSearch:
    def __init__(self, web_search, embedder, answerer, fetch=fetch_url,
                 top_n: int = 4, expander=None, max_subqueries: int = 5) -> None:
        self.web_search = web_search
        self.embedder = embedder
        self.answerer = answerer
        self.fetch = fetch
        self.top_n = top_n
        self.expander = expander
        self.max_subqueries = max_subqueries

    def run(self, query: str, explore: bool = False) -> SmartResult:
        # 搜尋層失敗（SourceUnavailable 等）向外拋 → 由路由攔成「搜尋失敗」（同階段 9）。
        results = self._collect(query, explore)
        if not results:
            return SmartResult(results=[])   # 查無：由頁面顯示，不整理（無材料可整理）

        # 整理層：排序＋抓取＋合成任一失敗 → 保留（原序）結果、附友善訊息（教訓 3）。
        try:
            ranked = self._rank(query, results)
            passages, sources = self._gather(ranked)
            text = self.answerer.answer(query, passages, "繁體中文")
            if _is_no_material(text):        # 說沒材料就別自相矛盾列來源（教訓 7）
                return SmartResult(overview=text, no_material=True, results=ranked)
            return SmartResult(overview=text, sources=sources, results=ranked)
        except Exception:                    # noqa: BLE001 - 整理是加值，掛了仍要給結果
            return SmartResult(results=results, overview_error=_OVERVIEW_ERR)

    def _collect(self, query: str, explore: bool) -> list[SearchResult]:
        """單 query（增量 b）或多角度 fan-out＋合併去重（explore／spec 011）。"""
        if not (explore and self.expander):
            return list(self.web_search.search(query))
        try:
            subs = self.expander.expand(query)
        except Exception:  # noqa: BLE001 - 拆解失敗退回單 query（教訓 3）
            subs = []
        angles: list[str] = []
        for a in [query, *subs]:               # 原 query 一定納入
            if a and a not in angles:
                angles.append(a)
        angles = angles[: self.max_subqueries]  # 硬上限（成本閘）
        merged: list[SearchResult] = []
        seen: set[str] = set()
        for a in angles:
            for r in self.web_search.search(a):
                key = _norm_url(r.url)
                if key and key not in seen:
                    seen.add(key)
                    merged.append(r)
        return merged

    def _rank(self, query: str, results: list[SearchResult]) -> list[SearchResult]:
        qv = self.embedder.embed(query)
        scored = []
        for i, r in enumerate(results):
            rv = self.embedder.embed(f"{r.title} {r.snippet}".strip())
            scored.append((cosine(qv, rv), i, r))
        # 相似度高者在前；同分保持搜尋後端原序（stable：以原 index 為次鍵升序）。
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [r for _, _, r in scored]

    def _gather(self, ranked: list[SearchResult]):
        passages: list[CorpusEntry] = []
        sources: list[Source] = []
        for n, r in enumerate(ranked[: self.top_n], 1):
            try:
                item = self.fetch(r.url)
                body = (item.abstract or "").strip()
            except Exception:                # noqa: BLE001 - 單則抓不到退回 snippet
                body = ""
            body = body or (r.snippet or "").strip() or r.title
            passages.append(CorpusEntry(entry_id=n, title=r.title, url=r.url,
                                        headline=r.title, body=body))
            sources.append(Source(n=n, title=r.title, url=r.url))
        return passages, sources
