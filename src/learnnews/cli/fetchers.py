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


# 預設來源（2026-07-23 依真實可用性盤點，見 history/005）：
# arXiv API（https，依投稿日排序）＋ HF Daily Papers ＋ Google News AI（廣度：真實新聞）。
# Semantic Scholar 因 free 端點持續 429 已移除（改由使用者自行加入並自架/退避）。
_ARXIV = ("https://export.arxiv.org/api/query?search_query=cat:{cat}"
          "&sortBy=submittedDate&sortOrder=descending&max_results=25")

DEFAULT_SOURCES = [
    Source("arxiv-cs", "arXiv cs.LG（機器學習）", "paper", "arxiv_api",
           _ARXIV.format(cat="cs.LG")),
    Source("arxiv-cl", "arXiv cs.CL（自然語言）", "paper", "arxiv_api",
           _ARXIV.format(cat="cs.CL")),
    Source("hf-papers", "Hugging Face Daily Papers", "paper", "hf_papers",
           "https://huggingface.co/api/daily_papers"),
    Source("gnews-ai", "Google News：AI（新聞）", "news", "rss",
           "https://news.google.com/rss/search?q=artificial+intelligence+when:2d&hl=en-US"),
]
