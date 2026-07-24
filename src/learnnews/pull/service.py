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
from ..summarize.article import ArticleBuilder, build_articles
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

        # 預設並行產散文；--raw（with_summary=False）完全不呼叫後端（SC-006/007）
        if with_summary:
            arts = build_articles(
                self.article_builder, [(s.item, s.matched_topic) for s in top],
                with_image=with_image, ai_image=ai_image)
        else:
            arts = [None] * len(top)
        entries: list[PullEntry] = [
            PullEntry(item=s.item, rank=rank, relevance_score=s.score, article=a)
            for rank, (s, a) in enumerate(zip(top, arts), start=1)]

        return self._finish(topic, entries, truncated, missing)

    def _finish(self, topic, entries, truncated, missing):
        result = PullResult(topic=topic, entries=entries,
                            truncated_count=truncated, missing_sources=missing)
        _log.info("拉取完成", extra={"extra": {
            "topic": topic, "entries": len(entries), "truncated": truncated,
            "missing_sources": missing, "is_empty": result.is_empty}})
        return result

    def pull_stream(self, topic, adapters, limit=6, with_image=True, since=None):
        """串流版：逐步 yield 進度事件，文章寫好一則即推一則（供 web SSE 即時回饋）。

        事件：{"type":"stage","text":…} / {"type":"card","entry":PullEntry,"progress":"k/n"}
             / {"type":"empty"} / {"type":"done"}。embedding/排序的失敗會往上拋，由呼叫端處理。
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        since = since or datetime(1970, 1, 1)
        collected, missing = [], []
        for adapter in adapters:
            try:
                collected.extend(adapter.fetch(since))
            except SourceUnavailable:
                missing.append(adapter.name)
        collected = [it for it in collected if it.has_source_link()]
        miss = f"（缺漏 {('、'.join(missing))}）" if missing else ""
        yield {"type": "stage", "text": f"從 {len(adapters)} 個來源取得 {len(collected)} 則候選{miss}…"}

        clusters = deduplicate(collected, embedder=self.embedder,
                               threshold=self.dedup_threshold)
        canonicals = [c for c in (DigestBuilder._canonical(g) for g in clusters)
                      if c is not None]
        yield {"type": "stage", "text": f"跨源去重成 {len(canonicals)} 則，排序中…"}

        scored = self.ranker.rank(canonicals, [topic])
        top = scored[:limit]
        if not top:
            yield {"type": "empty"}
            return
        yield {"type": "stage", "text": f"取最相關 {len(top)} 則，並行消化中…"}

        with ThreadPoolExecutor(max_workers=min(8, len(top))) as ex:
            futs = {ex.submit(self.article_builder.build, s.item, s.matched_topic,
                              with_image, False): (rank, s)
                    for rank, s in enumerate(top, start=1)}
            done = 0
            for fut in as_completed(futs):
                rank, s = futs[fut]
                article = fut.result()
                done += 1
                yield {"type": "card",
                       "entry": PullEntry(item=s.item, rank=rank,
                                          relevance_score=s.score, article=article),
                       "progress": f"{done}/{len(top)}"}
        yield {"type": "done"}
