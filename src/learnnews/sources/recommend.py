"""場驅動來源推薦（spec 020）：撒網找進水口 → 驗證 feed → 場驅動排序 → 人訂閱。

串接既有零件、不重寫：`discover_feed`/`validate_feed`/`_feed_title`/`_source_id`（spec 008）、
可插拔 `WebSearch`（spec 009/016）、`list_field_attractors`＋`ensure_embeddings`＋`cosine`（spec 005/018）。
純函式、`http_get` 可注入（離線可測，教訓 1）；搜尋/抓取失敗攔成友善（教訓 3）。
候選短暫、不落庫——只有人按訂閱才走既有 `/sources/add` 進名冊（原則 5）。
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from ..ranking.embeddings import cosine
from ..rag.service import embedder_tag
from ..seed.fetch import default_http_get
from .base import SourceUnavailable
from .subscribe import _feed_title, _source_id, discover_feed, validate_feed

_DEFAULT_QUERIES = ("最佳 AI 部落格 2026", "best AI research blogs",
                    "top AI newsletters roundup")
_FIELD_REASON_MIN = 0.2   # 場驅動理由門檻（低於此不算「你冊封的出自它」）


@dataclass
class CandidateSource:
    domain: str
    homepage: str
    feed_url: str | None
    name: str
    reason: str
    field_score: float
    list_hits: int
    has_feed: bool
    already_subscribed: bool


def _domain(url: str) -> str:
    dom = urlparse(url or "").netloc.lower()
    return dom[4:] if dom.startswith("www.") else dom


def recommend_sources(web_search, embedder, repo, *, http_get=default_http_get,
                      queries=None, limit: int = 8) -> list[CandidateSource]:
    """撒網→抽網域→驗證 feed→場驅動排序，回候選清單（不落庫）。"""
    queries = list(queries) if queries else list(_DEFAULT_QUERIES)

    # 1. 撒網（一般搜尋、非 news 模式）；搜尋失敗 → SourceUnavailable（路由攔）
    results = []
    for q in queries:
        results.extend(web_search.search(q, news=False))
    if not results:
        return []

    # 2. 抽候選網域；跨結果重複＝list_hits
    agg: dict[str, dict] = {}
    order: list[str] = []
    for r in results:
        dom = _domain(r.url)
        if not dom:
            continue
        if dom not in agg:
            agg[dom] = {"snippet": r.snippet or "", "hits": 0}
            order.append(dom)
        agg[dom]["hits"] += 1

    subscribed_ids = {s.id for s in repo.list_sources()}

    # 3. feed 探測＋驗證（複用 spec 008）：死/幻覺丟棄、無 feed 標示保留
    candidates: list[CandidateSource] = []
    for dom in order:
        homepage = f"https://{dom}/"
        feed_url = None
        has_feed = False
        try:
            fu = discover_feed(homepage, http_get)
            if fu:
                items = validate_feed(fu, http_get)   # 可能拋 SourceUnavailable
                if not items:
                    continue                          # 探到但空＝幻覺 → 丟棄（FR-002）
                feed_url, has_feed = fu, True
        except SourceUnavailable:
            continue                                  # 死 feed → 丟棄（FR-002）
        except Exception:  # noqa: BLE001 — 單站掛掉不拖垮整批（同 digest build 韌性）
            continue
        name = ""
        if has_feed:
            try:
                name = _feed_title(http_get(feed_url))
            except Exception:  # noqa: BLE001
                name = ""
        name = name or dom
        already = has_feed and _source_id(feed_url) in subscribed_ids
        candidates.append(CandidateSource(
            domain=dom, homepage=homepage, feed_url=feed_url, name=name,
            reason="", field_score=0.0, list_hits=agg[dom]["hits"],
            has_feed=has_feed, already_subscribed=already))

    # 4. 場驅動分數（複用 spec 005/018）：候選文字對場的 cosine 最大值
    attractors = repo.list_field_attractors()
    if attractors and candidates:
        vecs = repo.ensure_embeddings(attractors, embedder, embedder_tag(embedder))
        for c in candidates:
            cv = embedder.embed(f"{c.name} {agg[c.domain]['snippet']}".strip())
            c.field_score = max(
                (cosine(cv, vecs[a.entry_id]) for a in attractors), default=0.0)

    # 5. 理由（依最強命中訊號）
    for c in candidates:
        c.reason = _reason(c)

    # 6. 排序：場驅動 ＞ 有活 feed ＞ 跨清單重複（FR-005）
    candidates.sort(key=lambda c: (c.field_score, c.has_feed, c.list_hits),
                    reverse=True)
    return candidates[:limit]


def _reason(c: CandidateSource) -> str:
    bits = []
    if c.field_score >= _FIELD_REASON_MIN:
        bits.append("★ 你冊封的種子/根因與它相近（場驅動）")
    if c.has_feed:
        bits.append("有活躍 feed")
    else:
        bits.append("無 RSS——靠 web 活水/收進補")
    if c.list_hits > 1:
        bits.append(f"在 {c.list_hits} 份清單重複出現")
    return "；".join(bits)
