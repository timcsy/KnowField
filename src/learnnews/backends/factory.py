"""依 Config 選擇 embedding／摘要後端：openai（真實 API）或 offline（stub）。"""

from __future__ import annotations

from ..config import Config
from ..ranking.embeddings import Embedder, HashingEmbedder
from ..summarize.llm import StubSummarizer, Summarizer


def make_embedder(config: Config) -> Embedder:
    if config.backend == "openai" and config.api_key:
        from .openai_api import OpenAIEmbedder
        return OpenAIEmbedder(config.api_base_url, config.api_key, config.embed_model)
    return HashingEmbedder()


def make_summarizer(config: Config) -> Summarizer:
    if config.backend == "openai" and config.api_key:
        from .openai_api import OpenAISummarizer
        return OpenAISummarizer(config.api_base_url, config.api_key, config.chat_model)
    return StubSummarizer()
