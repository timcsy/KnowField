"""可讀文章式消化（spec 003）。

Article 取代 Summary 為預設消化產物：一則材料 → 一篇可讀散文（忠實、不下結論）＋
可選配圖，每則保留一鍵原文（原則 3/4）。後端失敗優雅降級（FR-011）。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Protocol

from ..backends.openai_api import OpenAIError
from ..models import Article, Figure, Item

__all__ = ["Article", "Figure", "ArticleBackend", "StubArticleBackend",
           "ArticleBuilder", "build_articles"]


def build_articles(builder: "ArticleBuilder", pairs: list[tuple[Item, str]],
                   with_image: bool = True, ai_image: bool = False,
                   max_workers: int = 8) -> list[Article]:
    """並行消化多則（LLM 呼叫是 I/O bound，用執行緒池同時打，大幅省牆鐘時間）。
    順序與輸入一致。每則的失敗由 builder.build 內部降級處理，不中斷其他則。"""
    if not pairs:
        return []
    if len(pairs) == 1:
        return [builder.build(pairs[0][0], pairs[0][1],
                              with_image=with_image, ai_image=ai_image)]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(pairs))) as ex:
        return list(ex.map(
            lambda p: builder.build(p[0], p[1], with_image=with_image,
                                    ai_image=ai_image),
            pairs))


class ArticleBackend(Protocol):
    def write_article(self, title: str, abstract: str,
                      matched_topic: str) -> tuple[str, str]:
        """回傳 (整理過的新聞式標題, 散文本體)。"""
        ...


class StubArticleBackend:
    """確定性散文（離線、可測）。只依原文標題/前文，不捏造、不下結論。
    離線無法真正「整理」標題，headline 退回原標題（渲染端會避免重複顯示）。"""

    def write_article(self, title: str, abstract: str,
                      matched_topic: str) -> tuple[str, str]:
        parts = [f"這篇在談「{title.strip()}」。"]
        if abstract.strip():
            parts.append(abstract.strip())
        if matched_topic:
            parts.append(f"它與你關注的「{matched_topic}」相關；完整細節見原文。")
        else:
            parts.append("完整細節見原文。")
        return title.strip(), " ".join(parts)


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
            headline, body = self.backend.write_article(
                item.title, item.abstract, matched_topic)
            degraded = False
        except OpenAIError as e:
            headline = item.title
            body = f"（消化暫不可用：{e}）標題：{item.title}"
            degraded = True

        figure = None
        if with_image and not degraded:
            if self.figure_extractor:
                figure = self.figure_extractor(item)          # 原文圖優先
            if figure is None and ai_image and self.ai_image_gen:
                figure = self.ai_image_gen(item)              # 退 AI 示意（必標示）

        return Article(item_id=item.id or 0, body=body, source_url=item.url,
                       headline=headline, figure=figure, degraded=degraded)
