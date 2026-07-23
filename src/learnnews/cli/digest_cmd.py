"""`learnnews digest` 指令（US1）。

核心 `run_digest` 與 CLI 解耦，供 contract 測試以注入 adapters 呼叫。
"""

from __future__ import annotations

from datetime import datetime

from ..backends.factory import make_embedder, make_summarizer
from ..config import Config
from ..digest.builder import DigestBuilder
from ..logging_setup import get_logger
from ..models import Digest
from ..ranking.interest_preset import preset_topics
from ..ranking.relevance import RelevanceRanker
from ..sources.base import SourceAdapter
from ..store.repository import Repository
from ..summarize.summarizer import SummaryBuilder
from .render import render

_log = get_logger("learnnews.cli")


def build_backend_builder(config: Config) -> DigestBuilder:
    """依設定組出 DigestBuilder（真實 OpenAI 後端或離線 stub）。"""
    embedder = make_embedder(config)
    summarizer = make_summarizer(config)
    _log.info("後端選定", extra={"extra": {
        "backend": config.backend,
        "embed_model": config.embed_model if config.backend == "openai" else "hashing",
        "chat_model": config.chat_model if config.backend == "openai" else "stub",
    }})
    return DigestBuilder(
        embedder=embedder,
        ranker=RelevanceRanker(embedder=embedder,
                               threshold=config.relevance_threshold),
        summary_builder=SummaryBuilder(backend=summarizer),
        dedup_threshold=config.dedup_similarity,
    )


def run_digest(
    repo: Repository,
    adapters: list[SourceAdapter],
    date: str,
    limit: int = 15,
    builder: DigestBuilder | None = None,
) -> Digest:
    """組裝當日匯整。若使用者已設定明講興趣，採用之；否則用預設清單（US1 獨立性）。"""
    profile = repo.get_interest_profile()
    topics = profile.explicit_topics or preset_topics()
    builder = builder or DigestBuilder()
    return builder.build(
        date=date,
        adapters=adapters,
        explicit_topics=topics,
        learned_weights=profile.learned_weights,
        limit=limit,
    )


def handle(args) -> int:
    from .fetchers import DEFAULT_SOURCES, build_adapters

    config = Config.from_env()
    repo = Repository(args.db)
    # 首次無來源則種入預設
    if not repo.list_sources():
        for s in DEFAULT_SOURCES:
            repo.upsert_source(s)
    sources = repo.list_sources(enabled_only=True)
    adapters = build_adapters(sources)
    date = args.date or datetime(2026, 7, 23).date().isoformat()
    builder = build_backend_builder(config)
    digest = run_digest(repo, adapters, date, limit=args.limit, builder=builder)
    fmt = "json" if args.json else args.format
    output = render(digest, fmt)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)
    repo.close()
    return 0  # 空匯整/缺漏來源仍為成功（已明確標示）
