"""`learnnews digest` 指令（US1）。

核心 `run_digest` 與 CLI 解耦，供 contract 測試以注入 adapters 呼叫。
"""

from __future__ import annotations

from datetime import datetime

from ..backends.factory import make_article_backend, make_ai_image_gen, make_embedder
from ..backends.openai_api import OpenAIError
from ..config import Config
from ..digest.builder import DigestBuilder
from ..logging_setup import get_logger
from ..media.figure_extract import extract_figure
from ..models import Digest
from ..ranking.interest_preset import preset_topics
from ..ranking.relevance import RelevanceRanker
from ..sources.base import SourceAdapter
from ..store.repository import Repository
from ..summarize.article import ArticleBuilder
from .render import render

_log = get_logger("learnnews.cli")


def build_backend_builder(config: Config) -> DigestBuilder:
    """依設定組出 DigestBuilder（真實 OpenAI 後端或離線 stub）。散文＋抓圖＋可選 AI 圖。"""
    embedder = make_embedder(config)
    _log.info("後端選定", extra={"extra": {
        "backend": config.backend,
        "embed_model": config.embed_model if config.backend == "openai" else "hashing",
        "chat_model": config.chat_model if config.backend == "openai" else "stub",
    }})
    article_builder = ArticleBuilder(
        backend=make_article_backend(config),
        figure_extractor=extract_figure,
        ai_image_gen=make_ai_image_gen(config),
    )
    return DigestBuilder(
        embedder=embedder,
        ranker=RelevanceRanker(embedder=embedder,
                               threshold=config.relevance_threshold),
        article_builder=article_builder,
        dedup_threshold=config.dedup_similarity,
        max_per_source=config.digest_max_per_source,
    )


def run_digest(
    repo: Repository,
    adapters: list[SourceAdapter],
    date: str,
    limit: int = 15,
    builder: DigestBuilder | None = None,
    with_summary: bool = True,
    ai_image: bool = False,
) -> Digest:
    """組裝當日匯整。若使用者已設定明講興趣，採用之；否則用預設清單（US1 獨立性）。
    with_summary=False（--raw）時仍取得材料，但不產散文（entry.article=None）。"""
    profile = repo.get_interest_profile()
    topics = profile.explicit_topics or preset_topics()
    builder = builder or DigestBuilder()
    return builder.build(
        date=date,
        adapters=adapters,
        explicit_topics=topics,
        learned_weights=profile.learned_weights,
        limit=limit,
        with_article=with_summary,
        with_image=with_summary,
        ai_image=ai_image,
    )


def handle(args) -> int:
    from .fetchers import DEFAULT_SOURCES, build_adapters

    config = Config.from_env()
    if getattr(args, "lang", None):
        config.article_lang = args.lang       # --lang 覆寫消化語言
    repo = Repository(args.db)
    # 首次無來源則種入預設
    if not repo.list_sources():
        for s in DEFAULT_SOURCES:
            repo.upsert_source(s)
    sources = repo.list_sources(enabled_only=True)
    adapters = build_adapters(sources, config)   # 傳 config → 啟用的 web 活水源生效（spec 015）
    date = args.date or datetime(2026, 7, 23).date().isoformat()
    builder = build_backend_builder(config)
    raw = getattr(args, "raw", False)
    ai_image = getattr(args, "ai_image", False)
    try:
        digest = run_digest(repo, adapters, date, limit=args.limit, builder=builder,
                            with_summary=not raw, ai_image=ai_image)
    except OpenAIError as e:
        _log.error("後端失敗", extra={"extra": {"reason": str(e)}})
        print(f"❌ 真實後端（OpenAI 格式 API）失敗：{e}\n"
              f"　可稍後重試，或設 LEARNNEWS_BACKEND=offline 用離線後端。")
        repo.close()
        return 1
    repo.save_digest(digest)  # 落庫供拉模式 --from-digest 使用（US2）
    # FR-009（spec 005）：存匯整時批次嵌入條目落庫，供 ask 問答；idempotent，查詢端不重算。
    # 嵌入失敗不擋 digest 主流程（匯整已產出）。
    try:
        from ..rag.service import embedder_tag
        emb = make_embedder(config)
        rows = repo.list_corpus_entries(today=True)
        repo.ensure_embeddings(rows, emb, embedder_tag(emb))
    except OpenAIError as e:
        _log.warning("匯整嵌入落庫失敗（不影響匯整）",
                     extra={"extra": {"reason": str(e)}})
    fmt = "json" if args.json else args.format
    output = render(digest, fmt, raw=raw)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)
    repo.close()
    return 0  # 空匯整/缺漏來源仍為成功（已明確標示）
