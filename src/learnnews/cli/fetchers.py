"""把 Source 列組成實際的 SourceAdapter（生產以 urllib 取得，失敗轉 SourceUnavailable）。

測試不經此處——contract/integration 測試直接以 fixtures 注入 fetch_raw。
"""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import datetime

from ..models import Source
from ..sources.arxiv import ArxivAdapter
from ..sources.base import SourceAdapter, SourceUnavailable
from ..sources.hf_papers import HFPapersAdapter
from ..sources.rss import RssAdapter
from ..sources.semantic_scholar import SemanticScholarAdapter

_ADAPTERS = {
    "arxiv_api": ArxivAdapter,
    "hf_papers": HFPapersAdapter,
    "semantic_scholar": SemanticScholarAdapter,
    "rss": RssAdapter,
    "email_ingest": RssAdapter,  # email-ingestion 產生 Atom feed，共用 RSS 解析
}


def _http_fetch_raw(endpoint: str):
    def fetch_raw(_since: datetime) -> str:
        req = urllib.request.Request(endpoint, headers={"User-Agent": "LearnNews/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise SourceUnavailable(f"取得 {endpoint} 失敗：{e}") from e
    return fetch_raw


def build_adapters(sources: list[Source]) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    for s in sources:
        cls = _ADAPTERS.get(s.access_method)
        if cls is None:
            continue
        adapters.append(cls(s.id, _http_fetch_raw(s.endpoint)))
    return adapters


# 預設來源（2026-07-23 依真實可用性盤點，決策見 knowledge/history/005、006）：
# 論文骨幹：arXiv API（https，依投稿日排序）＋ HF Daily Papers。
# 精選新聞（廣度差異化）：
#   策展週報：Import AI、Last Week in AI（訊噪比高，取代先前雜訊多的 Google News）；
#   日更產業新聞：Ars Technica AI（補週報的每日新鮮度，見 history/007）。
# Semantic Scholar 因 free 端點持續 429 已移除。
_ARXIV = ("https://export.arxiv.org/api/query?search_query=cat:{cat}"
          "&sortBy=submittedDate&sortOrder=descending&max_results=25")

DEFAULT_SOURCES = [
    Source("arxiv-cs", "arXiv cs.LG（機器學習）", "paper", "arxiv_api",
           _ARXIV.format(cat="cs.LG")),
    Source("arxiv-cl", "arXiv cs.CL（自然語言）", "paper", "arxiv_api",
           _ARXIV.format(cat="cs.CL")),
    Source("hf-papers", "Hugging Face Daily Papers", "paper", "hf_papers",
           "https://huggingface.co/api/daily_papers"),
    Source("import-ai", "Import AI（Jack Clark 策展）", "news", "rss",
           "https://importai.substack.com/feed"),
    Source("last-week-in-ai", "Last Week in AI（策展）", "news", "rss",
           "https://lastweekin.ai/feed"),
    Source("ars-ai", "Ars Technica AI（日更產業新聞）", "news", "rss",
           "https://arstechnica.com/ai/feed/"),
]
