"""RagService：載語料 → 確保嵌入 → 檢索 → 門檻 → 合成（可溯源）。

與 CLI 解耦，供測試以注入 embedder/answerer 呼叫（教訓 1）。溯源鐵律：來源清單由
檢索集合生成，不靠模型自律（research.md R4）。
"""

from __future__ import annotations

from ..ranking.embeddings import cosine
from .answerer import Answerer
from .types import CorpusEntry, RagAnswer, Scope, Source, Vector


def embedder_tag(embedder) -> str:
    """embedder 身分標記——讓不同 embedder 的向量共存不混比（data-model.md）。"""
    name = type(embedder).__name__
    if name == "HashingEmbedder":
        return f"hashing-{getattr(embedder, 'dim', 0)}"
    if name == "OpenAIEmbedder":
        return f"openai-{getattr(embedder, 'model', '')}"
    return name


class RagService:
    def __init__(self, repo, embedder, answerer: Answerer,
                 top_k: int = 6, min_score: float = 0.10) -> None:
        self.repo = repo
        self.embedder = embedder
        self.answerer = answerer
        self.top_k = top_k
        self.min_score = min_score

    def answer(self, question: str, scope: Scope | None = None,
               lang: str = "繁體中文") -> RagAnswer:
        scope = scope or Scope()
        entries = self.repo.list_corpus_entries(today=scope.today)
        if not entries:
            return RagAnswer(no_material=True)

        tag = embedder_tag(self.embedder)
        vecs: dict[int, Vector] = self.repo.ensure_embeddings(entries, self.embedder, tag)
        qvec = self.embedder.embed(question)

        scored = sorted(
            ((cosine(qvec, vecs[e.entry_id]), e) for e in entries),
            key=lambda t: t[0], reverse=True,
        )
        hits: list[CorpusEntry] = [e for s, e in scored if s >= self.min_score][: self.top_k]
        if not hits:
            # 查無相關：不呼叫合成後端、不產生任何內容/來源（FR-004、原則 3）
            return RagAnswer(no_material=True)

        text = self.answerer.answer(question, hits, lang)
        sources = [Source(n=i, title=e.title, url=e.url) for i, e in enumerate(hits, 1)]
        return RagAnswer(text=text, sources=sources)
