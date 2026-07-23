"""可讀文章式消化（spec 003）。

Article 取代 Summary 為預設消化產物：一則材料 → 一篇可讀散文（忠實、不下結論）＋
可選配圖，每則保留一鍵原文（原則 3/4）。後端失敗優雅降級（FR-011）。
"""

from __future__ import annotations

from typing import Callable, Protocol

from ..backends.openai_api import OpenAIError
from ..models import Article, Figure, Item

__all__ = ["Article", "Figure", "ArticleBackend", "StubArticleBackend", "ArticleBuilder"]


class ArticleBackend(Protocol):
    def write_article(self, title: str, abstract: str, matched_topic: str) -> str: ...


class StubArticleBackend:
    """確定性散文（離線、可測）。只依原文標題/前文，不捏造、不下結論。"""

    def write_article(self, title: str, abstract: str, matched_topic: str) -> str:
        parts = [f"這篇在談「{title.strip()}」。"]
        if abstract.strip():
            parts.append(abstract.strip())
        if matched_topic:
            parts.append(f"它與你關注的「{matched_topic}」相關；完整細節見原文。")
        else:
            parts.append("完整細節見原文。")
        return " ".join(parts)


# 抓圖／AI 圖為可注入的 callable，預設 None（US1 無圖）
FigureExtractor = Callable[[Item], "Figure | None"]
AIImageGen = Callable[[Item], "Figure | None"]


class ArticleBuilder:
    def __init__(
        self,
        backend: ArticleBackend | None = None,
        figure_extractor: FigureExtractor | None = None,
        ai_image_gen: AIImageGen | None = None,
    ) -> None:
        self.backend = backend or StubArticleBackend()
        self.figure_extractor = figure_extractor
        self.ai_image_gen = ai_image_gen

    def build(
        self,
        item: Item,
        matched_topic: str = "",
        with_image: bool = False,
        ai_image: bool = False,
    ) -> Article:
        # 散文：後端失敗 → 優雅降級為精簡呈現（FR-011），不中斷
        try:
            body = self.backend.write_article(item.title, item.abstract, matched_topic)
            degraded = False
        except OpenAIError as e:
            body = f"（消化暫不可用：{e}）標題：{item.title}"
            degraded = True

        figure = None
        if with_image and not degraded:
            if self.figure_extractor:
                figure = self.figure_extractor(item)          # 原文圖優先
            if figure is None and ai_image and self.ai_image_gen:
                figure = self.ai_image_gen(item)              # 退 AI 示意（必標示）

        return Article(item_id=item.id or 0, body=body,
                       source_url=item.url, figure=figure, degraded=degraded)
