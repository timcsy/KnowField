"""根因萃取後端（spec 010／階段 10）：對一則材料抽「為何 work 的根因」候選 why-node。

母概念 concepts/有吸引子的場：這是最有價值也最危險的一步（AI 很會生 plausible-BS）。故：
- 產候選時 **MUST 對自己 adversarial**——逐條試金石標 pass/fail、標霧詞旗標（folie à deux 解藥）。
- 只用材料內容、不杜撰；抽不出有把握的根因就 `no_material=True`（不硬編）。
- 候選只是候選——是否冊封成正式吸引子由人決定（原則 5，本後端不落庫、不冊封）。

離線 `StubExtractor`（確定性、試金石全「待驗」、零外部呼叫）；真實 `OpenAIExtractor`（既有
chat `_post`，urllib，不加 pip）。失敗拋 `SourceUnavailable`（路由攔成友善繁中）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from ..backends.openai_api import _post
from ..sources.base import SourceUnavailable

# 7 條試金石（concept：純度守門員）
TOUCHSTONES = ["預測力可證偽", "解釋反事實", "機制非相關", "會壓縮",
               "能重導生成", "追問不撞牆", "多源三角"]


@dataclass
class WhyNode:
    """一個 why-node（根因）——候選或已冊封的吸引子。"""

    id: int
    claim: str
    evidence_urls: list = field(default_factory=list)
    touchstones: list = field(default_factory=list)
    fog_flag: bool = False
    status: str = "candidate"          # 'candidate' | 'anointed'
    source_entry_id: int = 0
    created_at: str = ""


@dataclass
class Candidate:
    """候選 why-node（未冊封）：根因主張＋試金石自評＋霧詞旗標＋證據。"""

    claim: str = ""
    touchstones: list = field(default_factory=list)   # [{name, passed}]
    fog_flag: bool = False
    evidence: list = field(default_factory=list)      # 證據 url（由呼叫端補種子 url）
    no_material: bool = False


class RootCauseExtractor(Protocol):
    def extract(self, title: str, body: str) -> Candidate: ...


class StubExtractor:
    """離線確定性：回一個「待驗」候選（試金石全 passed=False）。零外部呼叫。"""

    def extract(self, title: str, body: str) -> Candidate:
        t = (title or "材料").strip()
        return Candidate(
            claim=f"（離線示意）「{t}」為何 work 的根因待驗——設定金鑰後由真實後端萃取。",
            touchstones=[{"name": n, "passed": False} for n in TOUCHSTONES],
            fog_flag=False, no_material=False)


class OpenAIExtractor:
    """OpenAI 格式 chat 抽根因＋逐條試金石自我反駁。`poster` 可注入供測試。"""

    _SYSTEM = (
        "你是根因分析助手。針對材料，抽出「這東西**為何** work 的根因」（機制層，不是換句話"
        "重述結果）。你**必須對自己的答案試著反駁**：逐條標示試金石是否通過，並標出是否躲在"
        "霧詞（更強表達力／expressive／captures／leverages 之類空話）後面。**只用材料內容、"
        "嚴禁杜撰**；若材料不足以有把握地抽出根因，回 no_material=true。\n"
        "只輸出 JSON（不要其他文字）：{\"claim\": \"根因主張（繁體中文一段）\", "
        "\"touchstones\": [{\"name\": \"預測力可證偽\", \"passed\": true/false}, …7 條], "
        "\"fog_flag\": true/false, \"no_material\": true/false}\n"
        f"試金石 7 條固定為：{TOUCHSTONES}"
    )

    def __init__(self, base_url: str, api_key: str, model: str, poster=_post) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._poster = poster

    def extract(self, title: str, body: str) -> Candidate:
        user = f"標題：{title}\n\n內容：\n{(body or '')[:3000]}"
        try:
            data = self._poster(self.base_url, "/chat/completions", self.api_key, {
                "model": self.model, "max_tokens": 700, "temperature": 0.3,
                "messages": [{"role": "system", "content": self._SYSTEM},
                             {"role": "user", "content": user}],
            })
            content = data["choices"][0]["message"]["content"].strip()
            content = _strip_fence(content)
            obj = json.loads(content)
        except SourceUnavailable:
            raise
        except Exception as e:  # noqa: BLE001 - 呼叫/解析失敗統一轉友善（路由攔）
            raise SourceUnavailable(f"根因萃取失敗：{e}") from e
        return Candidate(
            claim=(obj.get("claim") or "").strip(),
            touchstones=obj.get("touchstones") or [],
            fog_flag=bool(obj.get("fog_flag")),
            no_material=bool(obj.get("no_material")))


def _strip_fence(s: str) -> str:
    # 去掉可能的 ```json ... ``` 圍籬
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()
