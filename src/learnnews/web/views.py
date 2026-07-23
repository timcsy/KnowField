"""把領域物件轉成頁面用的最小資料（view models）。web 呈現層，不碰核心邏輯。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FigureView:
    url: str
    label: str
    is_ai: bool


@dataclass
class PageEntry:
    headline: str
    original_title: str      # 與 headline 不同時，顯示為副標（溯源）
    paragraphs: list[str] = field(default_factory=list)
    source_url: str = ""
    figure: FigureView | None = None

    @property
    def show_original(self) -> bool:
        return self.original_title.strip() != self.headline.strip()


def _paragraphs(body: str) -> list[str]:
    """散文本體切段（依空行或換行）。逸出交給模板（Jinja2 autoescape）。"""
    parts = re.split(r"\n\s*\n|\n", (body or "").strip())
    return [p.strip() for p in parts if p.strip()]


def entry_to_page(entry) -> PageEntry:
    """DigestEntry 或 PullEntry → PageEntry。無 article（--raw）時退回標題＋連結。"""
    item = entry.item
    a = entry.article
    if a is None:
        return PageEntry(headline=item.title, original_title=item.title,
                         paragraphs=[], source_url=item.url)
    fig = None
    if a.figure is not None:
        fig = FigureView(url=a.figure.url, label=a.figure.label(),
                         is_ai=(a.figure.kind == "AI 示意"))
    return PageEntry(
        headline=a.headline or item.title,
        original_title=item.title,
        paragraphs=_paragraphs(a.body),
        source_url=a.source_url or item.url,
        figure=fig,
    )
