"""場對新材料做工（spec 018／階段 15）：讓一則材料在你的吸引子場裡跑一次 forward pass。

護城河核心——Google 架構上做不到，因為它沒有「你的場」。材料進來 → 找最近的**冊封吸引子**
（種子＋已冊封根因）→ grounded 判**延伸/牴觸/無關聯**；離所有吸引子都遠 → **成核候選**（新地基）。
拆開的 optimizer：AI 算關係（梯度）、**人決定**（optimizer step）——**場不自動改**（原則 5）。

判關係可插拔（`StubRelationJudge` 離線／`OpenAIRelationJudge` 真實）；grounded、牴觸明說、不杜撰
（教訓 7）。門檻沿用 `rag_min_score` 尺度校準（教訓 4）。relate **不寫任何庫**。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from ..backends.openai_api import _post
from ..rag.service import embedder_tag
from ..ranking.embeddings import cosine
from ..rag.types import CorpusEntry
from ..sources.base import SourceUnavailable

_MIN_BODY = 30   # 材料太短（<此）視為無法有意義關聯


@dataclass
class FieldRelation:
    kind: str                       # extend|contradict|none|nucleate|empty
    attractor: CorpusEntry | None = None
    reason: str = ""
    score: float = 0.0


class RelationJudge(Protocol):
    def judge(self, material_title: str, material_body: str, attractor_claim: str) -> dict: ...


class StubRelationJudge:
    """離線確定性：回一個「待驗」的延伸關係。零外部呼叫。"""

    def judge(self, material_title: str, material_body: str, attractor_claim: str) -> dict:
        return {"kind": "extend", "reason": "（離線示意）關係待驗——設定金鑰後由真實後端判定。"}


class OpenAIRelationJudge:
    """OpenAI 格式 chat 判材料與一條根因的關係。`poster` 可注入供測試。"""

    _SYSTEM = (
        "你判斷一則材料與使用者冊封的一條『根因』的關係。只依**這則材料**與**這條根因主張**判定："
        "material 是**延伸**（extend：順著它、補強/推進/舉例）、**牴觸**（contradict：與它相反、"
        "反例、結論相左）、還是**無明顯關聯**（none）。**牴觸要明說、不要含糊帶過**。"
        "只用給的兩段內容、**嚴禁杜撰**；不確定或其實無關就回 none。"
        "只輸出 JSON：{\"kind\": \"extend|contradict|none\", \"reason\": \"繁體中文一句、指出依據\"}"
    )

    def __init__(self, base_url: str, api_key: str, model: str, poster=_post) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._poster = poster

    def judge(self, material_title: str, material_body: str, attractor_claim: str) -> dict:
        user = (f"根因主張：{attractor_claim}\n\n"
                f"材料標題：{material_title}\n材料內容：\n{(material_body or '')[:2500]}")
        try:
            data = self._poster(self.base_url, "/chat/completions", self.api_key, {
                "model": self.model, "max_tokens": 300, "temperature": 0.2,
                "messages": [{"role": "system", "content": self._SYSTEM},
                             {"role": "user", "content": user}],
            })
            content = _strip_fence(data["choices"][0]["message"]["content"].strip())
            obj = json.loads(content)
        except SourceUnavailable:
            raise
        except Exception as e:  # noqa: BLE001 - 呼叫/解析失敗 → 友善（路由攔）
            raise SourceUnavailable(f"判關係失敗：{e}") from e
        kind = obj.get("kind")
        if kind not in ("extend", "contradict", "none"):
            kind = "none"
        return {"kind": kind, "reason": (obj.get("reason") or "").strip()}


class FieldRelate:
    def __init__(self, embedder, judge, repo, min_score: float = 0.10) -> None:
        self.embedder = embedder
        self.judge = judge
        self.repo = repo
        self.min_score = min_score

    def relate(self, title: str, body: str, exclude_url: str | None = None) -> FieldRelation:
        attractors = [a for a in self.repo.list_field_attractors()
                      if not (exclude_url and a.url == exclude_url)]
        if not attractors:
            return FieldRelation(kind="empty",
                                 reason="你的場還是空的——先在『根因』冊封幾條、或『收進』幾則種子。")
        tag = embedder_tag(self.embedder)
        vecs = self.repo.ensure_embeddings(attractors, self.embedder, tag)
        mvec = self.embedder.embed(f"{title}\n{body}".strip())
        scored = [(cosine(mvec, vecs[a.entry_id]), a) for a in attractors]
        scored.sort(key=lambda t: t[0], reverse=True)
        top_score, top = scored[0]

        if top_score < self.min_score:
            # 離所有吸引子都遠＝成長前緣。材料太短則無法有意義關聯。
            if len((body or "").strip()) < _MIN_BODY:
                return FieldRelation(kind="empty", score=top_score,
                                     reason="材料太短，無法有意義關聯。")
            return FieldRelation(
                kind="nucleate", score=top_score,
                reason="這則離你場裡所有吸引子都遠——可能是個新地基。要不要為它萃取根因/收進？")

        rel = self.judge.judge(title, body, top.body)   # grounded 判關係（拋 SourceUnavailable → 路由攔）
        return FieldRelation(kind=rel["kind"], attractor=top,
                             reason=rel.get("reason", ""), score=top_score)


def _strip_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()
