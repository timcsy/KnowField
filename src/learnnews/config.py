"""設定（YAGNI：dataclass ＋環境變數 ＋可選 .env，無外部設定框架）。

真實後端走使用者的 OpenAI 格式 API（chat completions ＋ embeddings）；金鑰與端點
由 .env／環境變數注入，預設仍保留離線 stub。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

SEEDS_DATE = "__種子__"   # 種子容器 digest 的哨兵 date（spec 006）


def load_dotenv(path: str = ".env") -> None:
    """極簡 .env 載入（不覆蓋既有環境變數）。無外部相依。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


@dataclass
class Config:
    db_path: str = "learnnews.db"
    digest_limit: int = 15               # SC-007 預設上限
    relevance_threshold: float = 0.10    # 低於此相關性即濾除
    dedup_similarity: float = 0.82       # 語義去重 cosine 門檻

    # 真實後端（OpenAI 格式 API）；未設 api_key 時退回離線 stub
    backend: str = "offline"             # "offline" | "openai"
    api_base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"
    article_lang: str = "繁體中文"      # 消化散文的輸出語言（預設繁中，可由 --lang 指定）

    # RAG 問答（spec 005）
    rag_top_k: int = 6                   # 取回條目數上限
    rag_min_score: float = 0.10          # 低於此相關度視為查無相關
    rag_explainer_weight: float = 1.5    # 解說文種子的檢索排序權重（spec 006，>1 才勝快訊）
    rag_root_weight: float = 2.0         # 已冊封根因的檢索權重（spec 012，>explainer＝重吸引子）

    # web 搜尋（spec 009）；未設時走離線 stub
    search_api_url: str = ""             # 搜尋 API 端點（如 Tavily）；空＝離線 stub
    search_api_key: str = ""
    smart_search_topn: int = 4           # 智慧搜尋抓內文整理的前 N 則（spec 010）
    search_news_time_range: str = "week" # web 活水 news 模式的時間窗（spec 016）：day/week/month
    explore_max_subqueries: int = 5      # 深入探索的子角度上限（spec 011，成本閘）
    trend_top_n: int = 8                 # 首頁熱詞 chips 數（spec 013）
    trend_recent_digests: int = 3        # 算熱詞取最近幾份匯整（spec 013）
    digest_max_per_source: int = 4       # 匯整每來源上限（防單一來源洗版、保多樣）

    @classmethod
    def from_env(cls, dotenv: str = ".env") -> "Config":
        load_dotenv(dotenv)
        api_key = os.environ.get("LEARNNEWS_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        base = (os.environ.get("LEARNNEWS_API_BASE")
                or os.environ.get("OPENAI_BASE_URL")
                or "https://api.openai.com/v1")
        backend = os.environ.get("LEARNNEWS_BACKEND", "")
        if not backend:
            backend = "openai" if api_key else "offline"
        return cls(
            db_path=os.environ.get("LEARNNEWS_DB", "learnnews.db"),
            digest_limit=int(os.environ.get("LEARNNEWS_LIMIT", "15")),
            backend=backend,
            api_base_url=base.rstrip("/"),
            api_key=api_key,
            chat_model=os.environ.get("LEARNNEWS_CHAT_MODEL", "gpt-4o-mini"),
            embed_model=os.environ.get("LEARNNEWS_EMBED_MODEL", "text-embedding-3-small"),
            article_lang=os.environ.get("LEARNNEWS_LANG", "繁體中文"),
            rag_top_k=int(os.environ.get("LEARNNEWS_RAG_TOPK", "6")),
            # 門檻依 embedder 尺度校準（experience 教訓 4）：真實嵌入 cosine 帶高、離線雜湊帶低。
            # 真跑實測（text-embedding-3-small）：命中≈0.6、鬆散相關 0.1–0.25、無關問題≤0.22。
            rag_min_score=float(os.environ.get(
                "LEARNNEWS_RAG_MINSCORE", "0.30" if backend == "openai" else "0.05")),
            rag_explainer_weight=float(
                os.environ.get("LEARNNEWS_RAG_EXPLAINER_WEIGHT", "1.5")),
            rag_root_weight=float(
                os.environ.get("LEARNNEWS_RAG_ROOT_WEIGHT", "2.0")),
            search_api_url=os.environ.get("LEARNNEWS_SEARCH_API_URL", ""),
            search_api_key=os.environ.get("LEARNNEWS_SEARCH_KEY", ""),
            smart_search_topn=int(os.environ.get("LEARNNEWS_SMART_TOPN", "4")),
            search_news_time_range=os.environ.get("LEARNNEWS_SEARCH_NEWS_RANGE", "week"),
            explore_max_subqueries=int(os.environ.get("LEARNNEWS_EXPLORE_MAXQ", "5")),
            trend_top_n=int(os.environ.get("LEARNNEWS_TREND_TOPN", "8")),
            trend_recent_digests=int(os.environ.get("LEARNNEWS_TREND_RECENT", "3")),
            digest_max_per_source=int(os.environ.get("LEARNNEWS_DIGEST_MAX_PER_SOURCE", "4")),
        )
