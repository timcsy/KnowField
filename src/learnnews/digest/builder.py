"""匯整組裝（US1、FR-002/003/004/006/007/011）。

流程：取得各來源 → 去重 → 濾除無原文者 → 興趣排序 → 取上限 → 對進榜條目封頂摘要
→ 組裝 Digest（含 truncated_count、missing_sources、is_empty）。缺漏不靜默（原則 V）。
"""

from __future__ import annotations

from datetime import datetime

from ..dedup.semantic import deduplicate
from ..logging_setup import get_logger
from ..models import Digest, DigestEntry, Item
from ..ranking.embeddings import Embedder, HashingEmbedder
from ..ranking.relevance import RelevanceRanker
from ..sources.base import SourceAdapter, SourceUnavailable
from ..summarize.article import ArticleBuilder

_log = get_logger("learnnews.digest")


class DigestBuilder:
    def __init__(
        self,
        embedder: Embedder | None = None,
        ranker: RelevanceRanker | None = None,
        article_builder: ArticleBuilder | None = None,
        dedup_threshold: float = 0.82,
    ) -> None:
        self.embedder = embedder or HashingEmbedder()
        self.ranker = ranker or RelevanceRanker(embedder=self.embedder)
        self.article_builder = article_builder or ArticleBuilder()
        self.dedup_threshold = dedup_threshold

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

        # 上限與截斷（SC-007，不靜默）
        top = scored[:limit]
        truncated = max(0, len(scored) - limit)

        entries: list[DigestEntry] = []
        for rank, s in enumerate(top, start=1):
            # --raw（with_article=False）：完全不呼叫散文/圖後端（SC-006）
            article = (self.article_builder.build(
                s.item, s.matched_topic, with_image=with_image, ai_image=ai_image)
                if with_article else None)
            entries.append(DigestEntry(
                item=s.item, rank=rank, relevance_score=s.score, article=article,
                matched_topic=s.matched_topic))

        digest = Digest(date=date, entries=entries, truncated_count=truncated,
                        missing_sources=missing)
        _log.info("匯整完成", extra={"extra": {
            "date": date, "entries": len(entries), "truncated": truncated,
            "missing_sources": missing, "is_empty": digest.is_empty}})
        return digest

    @staticmethod
    def _canonical(group: list[Item]) -> Item | None:
        """選代表條目：優先有原文連結、發布時間最早者。"""
        candidates = [it for it in group if it.has_source_link()]
        if not candidates:
            return None
        return min(candidates, key=lambda it: (it.published_at or datetime.max))
