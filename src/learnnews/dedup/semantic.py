"""去重語義層（FR-002）：對精確層後仍疑似重複者（改寫/翻譯），以 embedding
cosine 相似度做連通分量分群。標題共享實體詞元時加權（entity-aware，research.md R2）。"""

from __future__ import annotations

from ..models import Item
from ..ranking.embeddings import Embedder, HashingEmbedder, cosine, tokenize


def _entity_overlap_boost(a: Item, b: Item) -> float:
    ta = {t for t in tokenize(a.title) if len(t) > 1}
    tb = {t for t in tokenize(b.title) if len(t) > 1}
    if not ta or not tb:
        return 0.0
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return 0.05 * overlap  # 小幅加權


def cluster_semantic(
    groups: list[list[Item]],
    embedder: Embedder | None = None,
    threshold: float = 0.82,
) -> list[list[Item]]:
    """輸入精確層分群（每群以第一個為代表），合併語義相似的群。"""
    embedder = embedder or HashingEmbedder()
    reps = [g[0] for g in groups]
    vecs = embedder.embed_many([f"{it.title} {it.abstract}" for it in reps])  # 批次

    parent = list(range(len(groups)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            sim = cosine(vecs[i], vecs[j]) + _entity_overlap_boost(reps[i], reps[j])
            if sim >= threshold:
                union(i, j)

    merged: dict[int, list[Item]] = {}
    for idx, group in enumerate(groups):
        root = find(idx)
        merged.setdefault(root, [])
        merged[root].extend(group)
    return list(merged.values())


def deduplicate(
    items: list[Item],
    embedder: Embedder | None = None,
    threshold: float = 0.82,
) -> list[list[Item]]:
    """完整兩層去重：精確 → 語義。回傳事件群組清單。"""
    from .exact import group_exact

    exact_groups = group_exact(items)
    return cluster_semantic(exact_groups, embedder=embedder, threshold=threshold)
