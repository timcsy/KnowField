"""`knowfield ingest` 指令（spec 006）：把一篇經典/解說文收進知識庫成種子。

核心 `SeedService` 與 CLI 解耦；此處組後端、列印結果、攔抓取/後端失敗（教訓 3）。
"""

from __future__ import annotations

from ..backends.factory import make_article_backend, make_embedder
from ..backends.openai_api import OpenAIError
from ..config import Config
from ..logging_setup import get_logger
from ..seed.service import SeedService
from ..sources.base import SourceUnavailable
from ..store.repository import Repository
from ..summarize.article import ArticleBuilder

_log = get_logger("knowfield.cli")


def handle(args) -> int:
    config = Config.from_env()
    if getattr(args, "lang", None):
        config.article_lang = args.lang
    repo = Repository(args.db)
    builder = ArticleBuilder(backend=make_article_backend(config))
    service = SeedService(repo, builder, make_embedder(config))
    try:
        res = service.ingest(args.ref, explainer=getattr(args, "explainer", False))
    except (SourceUnavailable, OpenAIError) as e:
        _log.error("種子 ingest 失敗", extra={"extra": {"reason": str(e)}})
        print(f"❌ 收取失敗：{e}")
        repo.close()
        return 1
    repo.close()

    if res.status == "exists":
        print(f"已在庫：{res.title}")
        return 0
    cls = "解說文" if res.source_class == "explainer" else "一般"
    print(f"✅ 已收進知識庫：{res.title}（{cls}）\n   原文：{res.url}")
    return 0
