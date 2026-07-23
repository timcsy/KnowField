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
        try:
            with urllib.request.urlopen(endpoint, timeout=30) as resp:
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


DEFAULT_SOURCES = [
    Source("arxiv-cs", "arXiv cs（AI 相關）", "paper", "arxiv_api",
           "http://export.arxiv.org/api/query?search_query=cat:cs.LG&max_results=25"),
    Source("hf-papers", "Hugging Face Daily Papers", "paper", "hf_papers",
           "https://huggingface.co/api/daily_papers"),
    Source("s2-ai", "Semantic Scholar（AI）", "paper", "semantic_scholar",
           "https://api.semanticscholar.org/graph/v1/paper/search?query=large+language+model"),
]
