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


def _parse_queries(endpoint: str) -> list[str]:
    """web_search 源的 endpoint＝換行/逗號分隔的查詢清單。"""
    raw = (endpoint or "").replace(",", "\n").splitlines()
    return [q.strip() for q in raw if q.strip()]


def build_adapters(sources: list[Source], config=None) -> list[SourceAdapter]:
    """組 adapters。web_search 源（spec 015）只在有 config＋搜尋金鑰時建（否則跳過，FR-003）。"""
    adapters: list[SourceAdapter] = []
    for s in sources:
        if s.access_method == "web_search":
            # opt-in 金鑰閘：無 config（如 pull）或無搜尋金鑰 → 不觸發開放網路搜尋
            if config is None or not (config.search_api_url and config.search_api_key):
                continue
            from ..backends.factory import make_web_search
            from ..sources.websearch_adapter import WebSearchAdapter
            adapter: SourceAdapter = WebSearchAdapter(
                s.id, make_web_search(config), _parse_queries(s.endpoint),
                news=True, time_range=config.search_news_time_range)
        else:
            cls = _ADAPTERS.get(s.access_method)
            if cls is None:
                continue
            adapter = cls(s.id, _http_fetch_raw(s.endpoint))
        # 缺漏標示標具體來源（友善名），而非通用類名「rss」/「arxiv」
        adapter.name = s.name
        adapters.append(adapter)
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
    # 即時產品新聞＋社群討論（spec：補「論文骨幹＋週刊」抓不到的剛紅新聞，feed 皆 2026-07-25 實測活）
    Source("openai-blog", "OpenAI Blog（官方發布）", "news", "rss",
           "https://openai.com/blog/rss.xml"),
    Source("techcrunch-ai", "TechCrunch AI（即時產業新聞）", "news", "rss",
           "https://techcrunch.com/category/artificial-intelligence/feed/"),
    Source("verge-ai", "The Verge AI（產品新聞）", "news", "rss",
           "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    Source("hn-ai", "Hacker News（AI 發布與討論）", "blog", "rss",
           "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude+OR+Anthropic+OR+OpenAI+OR+Gemini"),
    Source("reddit-localllama", "Reddit r/LocalLLaMA（社群心得）", "blog", "rss",
           "https://www.reddit.com/r/LocalLLaMA/.rss"),
    # live web 活水（spec 015）：伸手到策展名冊外抓剛紅新聞。預設停用、需搜尋金鑰才生效（opt-in）。
    Source("web-ai-trends", "開放網路 AI 趨勢（需搜尋金鑰・opt-in）", "news", "web_search",
           "latest AI model release\nnew open-source LLM\nAI breakthrough announcement\n"
           "new AI product launch", enabled=False),
]
