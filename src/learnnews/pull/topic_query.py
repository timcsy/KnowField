"""主題查詢建構（research.md R1）。

可查詢來源（arXiv）：以主題建 search 查詢 URL，得更廣候選。
不可任意查詢的來源（HF、RSS）：用原 feed 取近期，再由 service 以相關性過濾。
"""

from __future__ import annotations

import urllib.parse

from ..models import Source

# 支援任意主題查詢的來源取得方式
QUERYABLE_METHODS = {"arxiv_api"}


def is_queryable(source: Source) -> bool:
    return source.access_method in QUERYABLE_METHODS


def arxiv_search_url(topic: str, max_results: int = 30) -> str:
    q = urllib.parse.quote_plus(f"all:{topic.strip()}")
    return (
        f"https://export.arxiv.org/api/query?search_query={q}"
        f"&sortBy=relevance&sortOrder=descending&max_results={max_results}"
    )


def endpoint_for(source: Source, topic: str, max_results: int = 30) -> str:
    """回傳拉取時該來源要用的端點：可查詢者換成主題查詢 URL，否則用原 endpoint。"""
    if source.access_method == "arxiv_api":
        return arxiv_search_url(topic, max_results)
    return source.endpoint
