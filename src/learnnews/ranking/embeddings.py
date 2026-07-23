"""Embedding 包裝。

介面 `Embedder` 可插拔（research.md R4）：MVP 預設為確定性、離線、零相依的
`HashingEmbedder`；生產可換 sentence-transformers 後端而不動去重/排序邏輯。
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

# 詞元：英數字串，或單一 CJK 字元（讓中文也能切）
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[一-鿿]")

Vector = list[float]


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> Vector: ...


class HashingEmbedder:
    """把詞元雜湊到固定維度並 L2 正規化。確定性、無外部相依。"""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> Vector:
        vec = [0.0] * self.dim
        for tok in tokenize(text):
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        return _l2_normalize(vec)


def _l2_normalize(vec: Vector) -> Vector:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def cosine(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b))
