"""匯整組裝（US1、FR-002/003/004/006/007/011）。

流程：取得各來源 → 去重 → 濾除無原文者 → 興趣排序 → 取上限 → 對進榜條目封頂摘要
→ 組裝 Digest（含 truncated_count、missing_sources、is_empty）。缺漏不靜默（原則 V）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..dedup.semantic import deduplicate
from ..logging_setup import get_logger
from ..models import Digest, DigestEntry, Item
from ..ranking.embeddings import Embedder, HashingEmbedder
from ..ranking.relevance import RelevanceRanker
from ..sources.base import SourceAdapter, SourceUnavailable
from ..summarize.article import ArticleBuilder, build_articles

_log = get_logger("learnnews.digest")


def _cap_per_source(scored: list, k: int | None) -> list:
    """每來源上限：保序取用，單一 source_id 最多 k 則——防單一 prolific 來源洗版。
    k 為 None/0 → 不設限。"""
    if not k or k <= 0:
        return list(scored)
    counts: dict = {}
    out = []
    for s in scored:
        sid = getattr(s.item, "source_id", "")
        if counts.get(sid, 0) >= k:
            continue
        counts[sid] = counts.get(sid, 0) + 1
        out.append(s)
    return out


class DigestBuilder:
    def __init__(
        self,
        embedder: Embedder | None = None,
        ranker: RelevanceRanker | None = None,
        article_builder: ArticleBuilder | None = None,
        dedup_threshold: float = 0.82,
        max_per_source: int | None = 4,
    ) -> None:
        self.embedder = embedder or HashingEmbedder()
        self.ranker = ranker or RelevanceRanker(embedder=self.embedder)
        self.article_builder = article_builder or ArticleBuilder()
        self.dedup_threshold = dedup_threshold
        self.max_per_source = max_per_source

    def build(
        self,
        date: str,
        adapters: list[SourceAdapter],
        explicit_topics: list[str],
        learned_weights: dict[str, float] | None = None,
        limit: int = 15,
        since: datetime | None = None,
        with_article: bool = True,
        with_image: bool = True,
        ai_image: bool = False,
    ) -> Digest:
        since = since or datetime(1970, 1, 1)
        collected: list[Item] = []
        missing: list[str] = []

        for adapter in adapters:
            try:
                items = adapter.fetch(since)
                collected.extend(items)
            except SourceUnavailable as e:
                # 缺漏不靜默：記入 missing_sources 並繼續（FR-011、原則 V）
                missing.append(adapter.name)
                _log.warning("來源缺漏", extra={"extra": {
                    "source": adapter.name, "reason": str(e)}})

        # FR-006：無原文連結者不得進匯整
        collected = [it for it in collected if it.has_source_link()]

        # 去重（FR-002）
        clusters = deduplicate(collected, embedder=self.embedder,
                               threshold=self.dedup_threshold)
        canonicals = [self._canonical(group) for group in clusters]
        canonicals = [c for c in canonicals if c is not None]

        # 興趣過濾與排序（FR-003）
        scored = self.ranker.rank(canonicals, explicit_topics, learned_weights)

        # 每來源上限：單一來源不得洗版，保匯整跨來源多樣（spec 015 後修）
        scored = _cap_per_source(scored, self.max_per_source)

        # 上限與截斷（SC-007，不靜默）
        top = scored[:limit]
        truncated = max(0, len(scored) - limit)

        # 消化：預設並行（--raw 時完全不呼叫散文/圖後端，SC-006）
        if with_article:
            arts = build_articles(
                self.article_builder, [(s.item, s.matched_topic) for s in top],
                with_image=with_image, ai_image=ai_image)
        else:
            arts = [None] * len(top)
        entries: list[DigestEntry] = [
            DigestEntry(item=s.item, rank=rank, relevance_score=s.score,
                        article=a, matched_topic=s.matched_topic)
            for rank, (s, a) in enumerate(zip(top, arts), start=1)]

        digest = Digest(date=date, entries=entries, truncated_count=truncated,
                        missing_sources=missing)
        _log.info("匯整完成", extra={"extra": {
            "date": date, "entries": len(entries), "truncated": truncated,
            "missing_sources": missing, "is_empty": digest.is_empty}})
        return digest

    @staticmethod
    def _canonical(group: list[Item]) -> Item | None:
        """選代表條目：優先有原文連結、發布時間最早者。

        published_at 可能混時區（atom/arxiv aware、rss/None naive）——排序前正規化成
        naive UTC，否則 min() 會拋「can't compare offset-naive and offset-aware」。
        """
        candidates = [it for it in group if it.has_source_link()]
        if not candidates:
            return None

        def _key(it: Item):
            dt = it.published_at or datetime.max
            if dt.tzinfo is not None:                # aware → naive UTC，才能與 naive 比較
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        return min(candidates, key=_key)
