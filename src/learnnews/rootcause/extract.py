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
    ladder: list = field(default_factory=list)        # why 階梯：表面→bedrock（每層一句）


@dataclass
class Candidate:
    """候選 why-node（未冊封）：根因主張（bedrock aha）＋why 階梯＋試金石自評＋霧詞旗標＋證據。"""

    claim: str = ""
    touchstones: list = field(default_factory=list)   # [{name, passed}]
    fog_flag: bool = False
    evidence: list = field(default_factory=list)      # 證據 url（由呼叫端補種子 url）
    no_material: bool = False
    ladder: list = field(default_factory=list)        # 表面 why → 更深 → bedrock（逐層挖）


class RootCauseExtractor(Protocol):
    def extract(self, title: str, body: str) -> Candidate: ...


class StubExtractor:
    """離線確定性：回一個「待驗」候選（含示意 why 階梯、試金石全 passed=False）。零外部呼叫。"""

    def extract(self, title: str, body: str) -> Candidate:
        t = (title or "材料").strip()
        return Candidate(
            claim=f"（離線示意）「{t}」的 bedrock 根因待驗——設定金鑰後由真實後端遞迴挖到底。",
            ladder=[f"（表面）「{t}」怎麼做的",
                    "（更深）為什麼這樣做會 work",
                    "（bedrock 待驗）落到數學必然／資源限制／資訊理論極限"],
            touchstones=[{"name": n, "passed": False} for n in TOUCHSTONES],
            fog_flag=False, no_material=False)


class OpenAIExtractor:
    """OpenAI 格式 chat 抽根因＋逐條試金石自我反駁。`poster` 可注入供測試。"""

    _SYSTEM = (
        "你是根因分析助手。目標**不是**給一個過得去的表面理由，而是**挖到 bedrock（底層邏輯）**、"
        "逼出那個讓一堆表面事實同時 click 的 **aha 洞見**。\n"
        "方法——**遞迴追問**：先講機制層的 why，接著對它再問「那**這個**又為什麼成立？」，"
        "**一層一層往下挖**，直到撞到**無法再化約的原始層**：數學必然／資源（算力/頻寬/樣本）限制／"
        "資訊理論極限／最佳化壓力。**不到原始層不准停**。\n"
        "紀律：① 若你發現自己在用**霧詞**（更強表達力／expressive／captures／leverages／"
        "rich representations 之類空話），那是還沒挖到底的訊號——**再往下挖一層**，別拿霧詞交卷。"
        "② `claim` 必須是**最底層的那個 aha**（能反推出表面現象、能重新推導/生成，不是換句話重述結果）。"
        "③ **只用材料內容、嚴禁杜撰**；若材料本身留一手、挖不到有把握的 bedrock，回 no_material=true"
        "（誠實承認挖不到，勝過編一個假的深洞見）。\n"
        "④ 對自己的 claim **試著反駁**，逐條標試金石是否通過。\n"
        "只輸出 JSON（不要其他文字）：{"
        "\"ladder\": [\"表面 why\", \"更深一層\", \"…\", \"bedrock（原始層）\"], "
        "\"claim\": \"最底層的 aha 洞見（繁體中文一段，就是 ladder 最後一層的精煉）\", "
        "\"touchstones\": [{\"name\": \"預測力可證偽\", \"passed\": true/false}, …7 條], "
        "\"fog_flag\": true/false, \"no_material\": true/false}\n"
        f"試金石 7 條固定為：{TOUCHSTONES}（第 6 條『追問不撞牆』特別重要：淺解釋很快撞霧詞，"
        "深解釋落到原始層）"
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
        ladder = [str(x).strip() for x in (obj.get("ladder") or []) if str(x).strip()]
        return Candidate(
            claim=(obj.get("claim") or "").strip(),
            ladder=ladder,
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
