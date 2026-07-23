"""`learnnews pull` 指令（US1＋US2）。

核心 `run_pull` 與 CLI 解耦，供 contract 測試以注入 adapters 呼叫。
"""

from __future__ import annotations

from ..backends.factory import make_article_backend, make_ai_image_gen, make_embedder
from ..backends.openai_api import OpenAIError
from ..config import Config
from ..logging_setup import get_logger
from ..media.figure_extract import extract_figure
from ..pull.service import PullService
from ..pull.topic_query import endpoint_for
from ..pull.types import PullResult
from ..ranking.relevance import RelevanceRanker
from ..sources.base import SourceAdapter
from ..store.repository import Repository
from ..summarize.article import ArticleBuilder
from .pull_render import render

_log = get_logger("learnnews.cli")


def build_backend_pull_service(config: Config) -> PullService:
    embedder = make_embedder(config)
    article_builder = ArticleBuilder(
        backend=make_article_backend(config),
        figure_extractor=extract_figure,
        ai_image_gen=make_ai_image_gen(config),
    )
    return PullService(
        embedder=embedder,
        ranker=RelevanceRanker(embedder=embedder, threshold=config.relevance_threshold),
        article_builder=article_builder,
        dedup_threshold=config.dedup_similarity,
    )


def build_pull_adapters(sources, topic: str, max_results: int = 30) -> list[SourceAdapter]:
    """為每個來源建拉取 adapter：可查詢者換成主題查詢 URL，其餘用原 feed。"""
    from .fetchers import _ADAPTERS, _http_fetch_raw

    adapters: list[SourceAdapter] = []
    for s in sources:
        cls = _ADAPTERS.get(s.access_method)
        if cls is None:
            continue
        url = endpoint_for(s, topic, max_results)
        adapters.append(cls(s.id, _http_fetch_raw(url)))
    return adapters


def run_pull(
    adapters: list[SourceAdapter],
    topic: str,
    limit: int = 30,
    with_summary: bool = True,
    service: PullService | None = None,
    ai_image: bool = False,
) -> PullResult:
    service = service or PullService()
    return service.pull(topic, adapters, limit=limit, with_summary=with_summary,
                        with_image=with_summary, ai_image=ai_image)


def _resolve_topic(args, repo: Repository) -> str | None:
    """US2：--from-digest <rank> → 讀最近匯整第 N 則的主題；否則用位置參數 topic。"""
    if getattr(args, "from_digest", None):
        entry = repo.get_last_digest_entry(args.from_digest)
        if entry is None:
            print(f"找不到最近匯整的第 {args.from_digest} 則。")
            return None
        return entry["matched_topic"] or entry["title"]
    return args.topic


def handle(args) -> int:
    from .fetchers import DEFAULT_SOURCES

    config = Config.from_env()
    repo = Repository(args.db)
    if not repo.list_sources():
        for s in DEFAULT_SOURCES:
            repo.upsert_source(s)

    topic = _resolve_topic(args, repo)
    if topic is None:
        repo.close()
        return 2

    with_summary = not args.raw
    ai_image = getattr(args, "ai_image", False)
    sources = repo.list_sources(enabled_only=True)
    adapters = build_pull_adapters(sources, topic, max_results=args.limit)
    service = build_backend_pull_service(config)
    try:
        result = run_pull(adapters, topic, limit=args.limit,
                          with_summary=with_summary, service=service, ai_image=ai_image)
    except OpenAIError as e:
        _log.error("後端失敗", extra={"extra": {"reason": str(e)}})
        print(f"❌ 真實後端（OpenAI 格式 API）失敗：{e}\n"
              f"　可稍後重試，或設 LEARNNEWS_BACKEND=offline 用離線後端。")
        repo.close()
        return 1

    fmt = "json" if args.json else args.format
    output = render(result, fmt, raw=args.raw)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)
    repo.close()
    return 0
