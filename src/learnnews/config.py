"""設定（YAGNI：dataclass ＋環境變數 ＋可選 .env，無外部設定框架）。

真實後端走使用者的 OpenAI 格式 API（chat completions ＋ embeddings）；金鑰與端點
由 .env／環境變數注入，預設仍保留離線 stub。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


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
        )
