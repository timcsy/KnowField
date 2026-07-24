"""種子測試共用：假 http 回應（離線，教訓 1）。"""

from __future__ import annotations

from learnnews.sources.base import SourceUnavailable

ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<id>http://arxiv.org/abs/1706.03762v5</id>
<title>Attention Is All You Need</title>
<summary>We propose the Transformer, a model architecture relying entirely on attention
mechanisms for sequence transduction, dispensing with recurrence and convolutions.</summary>
<link rel="alternate" href="http://arxiv.org/abs/1706.03762v5"/>
</entry>
</feed>"""


def article_html(title: str, body: str) -> str:
    return (f"<html><head><title>{title}</title></head><body><nav>menu junk</nav>"
            f"<p>{body}</p></body></html>")


def http_arxiv(url: str) -> str:
    """任何 url 都回同一篇 arXiv Atom（測 arXiv 路徑）。"""
    return ARXIV_ATOM


def http_html(title: str, body: str):
    """回傳一個 http_get，任何 url 都回同一篇 HTML（測 URL 路徑）。"""
    html = article_html(title, body)
    return lambda url: html


def http_fail(url: str) -> str:
    raise SourceUnavailable("模擬取得失敗（404/網路）")
