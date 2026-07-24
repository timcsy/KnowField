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


def make_answerer(config: Config):
    """RAG 答案合成後端：真實走 OpenAI 格式 chat，否則離線 stub（spec 005）。"""
    if config.backend == "openai" and config.api_key:
        from .openai_api import OpenAIAnswerer
        return OpenAIAnswerer(config.api_base_url, config.api_key, config.chat_model)
    from ..rag.answerer import StubAnswerer
    return StubAnswerer()


def make_article_backend(config: Config):
    """散文後端：真實走 OpenAI 格式 chat，否則離線 stub。"""
    from ..summarize.article import StubArticleBackend
    if config.backend == "openai" and config.api_key:
        from .openai_api import OpenAIArticleWriter
        return OpenAIArticleWriter(config.api_base_url, config.api_key, config.chat_model,
                                   lang=config.article_lang)
    return StubArticleBackend()


def make_ai_image_gen(config: Config):
    """AI 示意圖產生器：真實走 OpenAI 格式 images，否則離線 stub。"""
    if config.backend == "openai" and config.api_key:
        from ..media.ai_image import OpenAIAIImage
        return OpenAIAIImage(config)
    from ..media.ai_image import StubAIImage
    return StubAIImage()
