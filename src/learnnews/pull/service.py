"""PullService（US1、FR-002/003/004/005/006/007/008）。

擴展搜尋 → 濾除無原文 → 去重 → 依**主題**相關性排序 → 取上限 →（可選）一句定位。
大量複用推模式：dedup、RelevanceRanker、SummaryBuilder、DigestBuilder._canonical。
"""

from __future__ import annotations

from datetime import datetime

from ..dedup.semantic import deduplicate
from ..digest.builder import DigestBuilder
from ..logging_setup import get_logger
from ..ranking.embeddings import Embedder, HashingEmbedder
from ..ranking.relevance import RelevanceRanker
from ..sources.base import SourceAdapter, SourceUnavailable
from ..summarize.article import ArticleBuilder
from .types import PullEntry, PullResult

_log = get_logger("learnnews.pull")


class PullService:
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

    def pull(
        self,
        topic: str,
        adapters: list[SourceAdapter],
        limit: int = 30,
        with_summary: bool = True,
        since: datetime | None = None,
        with_image: bool = True,
        ai_image: bool = False,
    ) -> PullResult:
        since = since or datetime(1970, 1, 1)
        collected = []
        missing: list[str] = []
        for adapter in adapters:
            try:
                collected.extend(adapter.fetch(since))
            except SourceUnavailable as e:
                missing.append(adapter.name)
                _log.warning("拉取來源缺漏", extra={"extra": {
                    "source": adapter.name, "topic": topic, "reason": str(e)}})

        # FR-005：無原文連結者不得進結果
        collected = [it for it in collected if it.has_source_link()]

        # 去重（FR-003）
        clusters = deduplicate(collected, embedder=self.embedder,
                               threshold=self.dedup_threshold)
        canonicals = [DigestBuilder._canonical(g) for g in clusters]
        canonicals = [c for c in canonicals if c is not None]

        # 依**主題**相關性過濾與排序（FR-004）
        scored = self.ranker.rank(canonicals, [topic])

        top = scored[:limit]
        truncated = max(0, len(scored) - limit)

        entries: list[PullEntry] = []
        for rank, s in enumerate(top, start=1):
            # 預設產可讀散文；--raw（with_summary=False）完全不呼叫後端（SC-006/007）
            article = (self.article_builder.build(
                s.item, s.matched_topic, with_image=with_image, ai_image=ai_image)
                if with_summary else None)
            entries.append(PullEntry(item=s.item, rank=rank,
                                     relevance_score=s.score, article=article))

        result = PullResult(topic=topic, entries=entries,
                            truncated_count=truncated, missing_sources=missing)
        _log.info("拉取完成", extra={"extra": {
            "topic": topic, "entries": len(entries), "truncated": truncated,
            "missing_sources": missing, "with_summary": with_summary,
            "is_empty": result.is_empty}})
        return result
