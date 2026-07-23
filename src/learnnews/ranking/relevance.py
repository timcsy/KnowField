"""興趣過濾與相關性排序（FR-003）。

以 embedding 語義相似度計算條目與**明講**興趣主題的相關性；learned_weights 僅對
明講主題的分數加成，**不新增比對主題**——因此被使用者移除的主題不會因學習而復活
（憲章原則 VI，明講優先）。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Item
from .embeddings import Embedder, HashingEmbedder, cosine


@dataclass
class Scored:
    item: Item
    score: float
    matched_topic: str


class RelevanceRanker:
    def __init__(
        self,
        embedder: Embedder | None = None,
        threshold: float = 0.10,
    ) -> None:
        self.embedder = embedder or HashingEmbedder()
        self.threshold = threshold

    def rank(
        self,
        items: list[Item],
        explicit_topics: list[str],
        learned_weights: dict[str, float] | None = None,
    ) -> list[Scored]:
        learned_weights = learned_weights or {}
        if not explicit_topics:
            # 無明講主題：不過濾，全數以中性分數保留（避免空跑）
            return [Scored(it, 1.0, "") for it in items]

        topic_vecs = {t: self.embedder.embed(t) for t in explicit_topics}
        scored: list[Scored] = []
        for item in items:
            vec = self.embedder.embed(f"{item.title} {item.abstract}")
            best_score = -1.0
            best_topic = ""
            for topic, tvec in topic_vecs.items():
                sim = cosine(vec, tvec)
                # 學習權重只對明講主題加成
                weighted = sim * (1.0 + max(0.0, learned_weights.get(topic, 0.0)))
                if weighted > best_score:
                    best_score = weighted
                    best_topic = topic
            if best_score >= self.threshold:
                scored.append(Scored(item, best_score, best_topic))
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored
