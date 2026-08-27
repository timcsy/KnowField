"""RagService：載語料 → 確保嵌入 → 檢索 → 門檻 → 合成（可溯源）。

與 CLI 解耦，供測試以注入 embedder/answerer 呼叫（教訓 1）。溯源鐵律：來源清單由
檢索集合生成，不靠模型自律（research.md R4）。
"""

from __future__ import annotations

from ..ranking.embeddings import cosine
from .answerer import Answerer
from .types import CorpusEntry, RagAnswer, Scope, Source, Vector


def _is_no_material(text: str) -> bool:
    """答案本身就是「沒有相關材料」的投降回應（無實質內容/無引用）→ 視為查無。"""
    t = (text or "").strip()
    return t.replace("。", "").replace(".", "").strip() == "沒有相關材料"


def embedder_tag(embedder) -> str:
    """embedder 身分標記——讓不同 embedder 的向量共存不混比（data-model.md）。"""
    name = type(embedder).__name__
    if name == "HashingEmbedder":
        return f"hashing-{getattr(embedder, 'dim', 0)}"
    if name == "OpenAIEmbedder":
        return f"openai-{getattr(embedder, 'model', '')}"
    return name


def retrieve_corpus(repo, embedder, query, top_k=6, min_score=0.10,
                    root_weight=2.0, explainer_weight=1.0, today=False,
                    entries=None, vectors=None):
    """找相關收進條目（spec 029）：取語料→向量→cosine→門檻→加權排序→top_k。

    純檢索、不合成。空語料/無相關→[]。RAG 與聊天共用（DRY）。離線可測（注入 stub embedder）。
    spec 076：`entries`／`vectors` 都給 ⇒ **換一個場**（站在某個專案裡時，語料是它的
    `knowledge/`）。⚠️ 兩個要一起給——外部的塊不共用 `entry_embeddings` 那個 id 空間。
    """
    # spec 076：`entries` ⇒ **換一個場**（開發模式站在某個專案裡時，語料是那個
    # 專案的 `knowledge/`）。⚠️ 預設 None ＝ 照舊，兩個既有呼叫點的行為一個字都不變。
    if entries is None:
        entries = repo.list_corpus_entries(today=today)
    if not entries:
        return []
    # ⚠️ 換場時**向量也要一起注入**：`ensure_embeddings` 寫的是 `entry_embeddings`，
    #    而那張表的 id 空間已經被 digest_entries（正）與 why_nodes（負）佔了
    #    ——外部的塊擠進去就是等著碰撞。它們的向量住自己的表，跟著重抓一起作廢。
    vecs = vectors if vectors is not None else repo.ensure_embeddings(
        entries, embedder, embedder_tag(embedder))
    qvec = embedder.embed(query)

    def _w(sc):
        return root_weight if sc == "root" else (explainer_weight if sc == "explainer" else 1.0)

    # 門檻用原始 cosine 把關（不被權重繞過）；權重只排序入選者（spec 006 R5）
    scored = [(cosine(qvec, vecs[e.entry_id]), e) for e in entries]
    scored = [(s, e) for s, e in scored if s >= min_score]
    scored.sort(key=lambda t: t[0] * _w(t[1].source_class), reverse=True)
    return [e for _, e in scored][:top_k]


class RagService:
    def __init__(self, repo, embedder, answerer: Answerer,
                 top_k: int = 6, min_score: float = 0.10,
                 explainer_weight: float = 1.0, root_weight: float = 2.0) -> None:
        self.repo = repo
        self.embedder = embedder
        self.answerer = answerer
        self.top_k = top_k
        self.min_score = min_score
        self.explainer_weight = explainer_weight
        self.root_weight = root_weight

    def _weight(self, source_class: str) -> float:
        # 已冊封根因＝最重的吸引子 > 解說文 > 一般（spec 012／concept：why 濃度最高）
        if source_class == "root":
            return self.root_weight
        if source_class == "explainer":
            return self.explainer_weight
        return 1.0

    def answer(self, question: str, scope: Scope | None = None,
               lang: str = "繁體中文") -> RagAnswer:
        scope = scope or Scope()
        hits: list[CorpusEntry] = retrieve_corpus(
            self.repo, self.embedder, question, top_k=self.top_k, min_score=self.min_score,
            root_weight=self.root_weight, explainer_weight=self.explainer_weight,
            today=scope.today)
        if not hits:
            # 空語料 or 查無相關：不呼叫合成後端、不產生任何內容/來源（FR-004、原則 3）
            return RagAnswer(no_material=True)

        text = self.answerer.answer(question, hits, lang)
        # 模型自己判「材料完全無關」時，別自相矛盾地還列來源（教訓 7：程式守約）。
        if _is_no_material(text):
            return RagAnswer(no_material=True)
        sources = [Source(n=i, title=e.title, url=e.url) for i, e in enumerate(hits, 1)]
        return RagAnswer(text=text, sources=sources)
