"""SeedService：把單篇材料收進 KB 成種子（原則 5 人冊封）。

與 CLI 解耦、抓取器 `http_get` 可注入（教訓 1）。交易式：抓取＋消化成功才寫入，
任一步失敗不寫半殘種子（FR-006）。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..sources.base import SourceUnavailable
from ..summarize.article import ArticleBuilder
from . import fetch as seedfetch
from .fetch import normalize_arxiv_id


@dataclass
class IngestResult:
    status: str            # 'ingested' | 'exists'
    title: str
    url: str
    source_class: str = "ordinary"


class SeedService:
    def __init__(self, repo, builder: ArticleBuilder, embedder, http_get=None) -> None:
        self.repo = repo
        self.builder = builder
        self.embedder = embedder
        self.http_get = http_get or seedfetch.default_http_get

    def ingest(self, ref: str, explainer: bool = False) -> IngestResult:
        arxiv_id = normalize_arxiv_id(ref)
        canonical = (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id
                     else (ref or "").strip())
        if not canonical:
            raise SourceUnavailable("請提供 arXiv ID 或文章 URL")

        # 去重（抓取前，同篇多寫法歸一）
        existing = self.repo.seed_exists(canonical)
        if existing is not None:
            return IngestResult(status="exists", title=existing, url=canonical)

        # 抓取（失敗拋 SourceUnavailable）
        if arxiv_id:
            item = seedfetch.fetch_arxiv_by_id(arxiv_id, self.http_get)
        else:
            item = seedfetch.fetch_url(canonical, self.http_get)

        # 消化（ArticleBuilder 吞 OpenAIError→degraded；種子不收半殘）
        article = self.builder.build(item, matched_topic="", with_image=False)
        if article.degraded:
            raise SourceUnavailable("消化後端暫時不可用，未收進知識庫，請稍後重試")

        source_class = "explainer" if explainer else "ordinary"
        entry_id = self.repo.ingest_seed(item, article, source_class)

        # 嵌入落庫（批次；沿用增量 1 的 ensure_embeddings）
        from ..rag.service import embedder_tag
        from ..rag.types import CorpusEntry
        ce = CorpusEntry(entry_id=entry_id, title=item.title, url=item.url,
                         headline=article.headline, body=article.body,
                         source_class=source_class)
        self.repo.ensure_embeddings([ce], self.embedder, embedder_tag(self.embedder))

        return IngestResult(status="ingested", title=item.title, url=item.url,
                            source_class=source_class)
