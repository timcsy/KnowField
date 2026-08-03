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


def make_web_search(config: Config):
    """web 搜尋後端：設了搜尋 API → 真實，否則離線 stub（spec 009）。"""
    if config.search_api_url and config.search_api_key:
        from ..search.websearch import ApiWebSearch
        return ApiWebSearch(config.search_api_url, config.search_api_key)
    from ..search.websearch import StubWebSearch
    return StubWebSearch()


def make_root_cause_extractor(config: Config):
    """根因萃取（spec 012）：真實走 OpenAI 格式 chat，否則離線確定性 stub。"""
    if config.backend == "openai" and config.api_key:
        from ..rootcause.extract import OpenAIExtractor
        return OpenAIExtractor(config.api_base_url, config.api_key, config.chat_model)
    from ..rootcause.extract import StubExtractor
    return StubExtractor()


def make_answerer(config: Config):
    """RAG 答案合成後端：真實走 OpenAI 格式 chat，否則離線 stub（spec 005）。"""
    if config.backend == "openai" and config.api_key:
        from .openai_api import OpenAIAnswerer
        return OpenAIAnswerer(config.api_base_url, config.api_key, config.chat_model)
    from ..rag.answerer import StubAnswerer
    return StubAnswerer()


def make_chat_backend(config: Config):
    """多輪對話後端（spec 022）：真實走 OpenAI 格式 chat，否則離線 stub。"""
    from ..chat.field_chat import StubChatBackend
    if config.backend == "openai" and config.api_key:
        from .openai_api import OpenAIChatBackend
        return OpenAIChatBackend(config.api_base_url, config.api_key, config.chat_model)
    return StubChatBackend()


def make_article_backend(config: Config):
    """散文後端：真實走 OpenAI 格式 chat，否則離線 stub。"""
    from ..summarize.article import StubArticleBackend
    if config.backend == "openai" and config.api_key:
        from .openai_api import OpenAIArticleWriter
        return OpenAIArticleWriter(config.api_base_url, config.api_key, config.chat_model,
                                   lang=config.article_lang)
    return StubArticleBackend()
