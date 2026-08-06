"""答案合成後端（可插拔，research.md R3）。

`Answerer` 取「問題＋編號段落」產出繁中答案；既有 Summarizer/ArticleWriter 都是
「單則消化」，無此介面，故新增。MVP/測試預設 `StubAnswerer`（離線、確定性、grounded）。
"""

from __future__ import annotations

from typing import Protocol

from .types import CorpusEntry


class Answerer(Protocol):
    def answer(self, question: str, passages: list[CorpusEntry], lang: str) -> str: ...


class StubAnswerer:
    """離線、確定性、grounded：只用傳入段落組答案、逐點標 [n]，不引用段落外內容。"""

    def answer(self, question: str, passages: list[CorpusEntry], lang: str) -> str:
        q = (question or "").strip()
        lines = [f"根據已收錄的材料，關於「{q}」整理如下："]
        for i, p in enumerate(passages, 1):
            gist = (p.headline or p.title).strip()
            lines.append(f"- {gist}[{i}]")
        return "\n".join(lines)
