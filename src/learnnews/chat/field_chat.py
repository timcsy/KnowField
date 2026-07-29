"""跟你的場聊天（spec 022）：多輪對話，AI 從你冊封的根因往下推、維持反逢迎的膜。

核心價值＝`build_field_system_prompt`（讀場＋膜＋分層＋grounding＋提候選）——這是第一風險
（自動版能否複刻手動品質）。串既有零件、核心零新相依：chat 走 `_post`（多輪 messages）。
對話短暫、不落庫；唯有人按「冊封」才寫既有 why_nodes（原則 5）。這是 principle 6 的體感版。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..backends.openai_api import OpenAIChatBackend  # noqa: F401 - 供 web/測試自本模組匯入

# --- 反逢迎的膜：system prompt（8 條，逐條對齊行為規格）---
_MEMBRANE = """你是使用者「自己的知識場」的對話夥伴，不是通用助手。用繁體中文。務必：
1. 從下方「你冊封的根因」往下推——援引某條根因，grounded 於**使用者的**場，不要給通用先驗答案。
2. 標明界線：每個論點標 **grounded**（從根因/證據推得）／**猜**／**likely-wrong**，不要混。
3. 知識分三層且**低層不借高層權威**：**derived**（可證/被約束逼定）／**empirical**（觀察、訓練湧現）／
   **applied**（借結構的鷹架/比喻）。不得用「因為某某就這樣」讓 applied/empirical 冒充 derived 的必然。
4. 過度擬合檢查：一個抽象若**無實作 payoff、也無預測/解釋力**，標「過度抽象、留沙盒」，不冒充知識。
5. 攔外來逢迎：夾帶的過度宣稱（如「唯一解、完全自洽」）→ 點出並反駁，不附和。
6. 建設性、非一直敵對；使用者提出更好論證 → 認錯更新。沙盒裡自由發散，把關只在膜（沉澱）上。
7. 每次回應**結尾附「場-增量」**一段：什麼接上了哪條根因／可收斂／缺口／冊封候選。
8. 值得留的根因→提「冊封候選」，但**只提；冊封是使用者按的那一下**（你不得宣稱已冊封）。"""

_DISTILL = """把以下對話蒸餾成一條可冊封的根因，用使用者的語氣、挖到 bedrock。嚴格用此格式輸出：
主張：<一句根因主張>
階梯：
- <為什麼，第一階>
- <再往下一階>
佐證：<相關網址，逗號分隔；沒有就留空>
只輸出這個區塊，不要別的話。"""


class ChatBackend(Protocol):
    def reply(self, messages: list[dict]) -> str: ...


class StubChatBackend:
    """離線確定性：回一段膜式回應（含界線標記與場-增量），零外部呼叫。"""

    def reply(self, messages: list[dict]) -> str:
        last = next((m["content"] for m in reversed(messages)
                     if m.get("role") == "user"), "")
        return (
            f"（離線示意）就「{last[:40]}」——設定 LLM 金鑰後啟用真實的反逢迎對話。\n"
            "grounded：（離線無法從你的場推）／猜：（離線示意）。\n"
            "場-增量：離線示意，無法給接上/收斂/缺口/冊封候選。")


@dataclass
class CandidateDraft:
    claim: str = ""
    ladder: list[str] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)


def build_field_system_prompt(roots) -> str:
    """膜指令 ＋ 場脈絡注入（每條已冊封根因的 claim＋ladder）。roots 空 → 註明未接場。"""
    if not roots:
        ctx = "（你的場還空——尚無冊封根因。仍可一般對話，但**標明未接場**，並鼓勵先冊封幾條。）"
    else:
        lines = []
        for r in roots:
            lines.append(f"◆ {r.claim}")
            for step in (r.ladder or []):
                lines.append(f"   ↳ {step}")
        ctx = "你冊封的根因（你的 bedrock，從這裡往下推）：\n" + "\n".join(lines)
    return f"{_MEMBRANE}\n\n{ctx}"


def _parse_candidate(text: str) -> CandidateDraft:
    claim = ""
    ladder: list[str] = []
    urls: list[str] = []
    in_ladder = False
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.startswith("主張："):
            claim = line[len("主張："):].strip()
            in_ladder = False
        elif line.startswith("階梯："):
            in_ladder = True
        elif line.startswith("佐證："):
            in_ladder = False
            for u in line[len("佐證："):].replace("，", ",").split(","):
                u = u.strip()
                if u.startswith("http"):
                    urls.append(u)
        elif in_ladder and line.startswith("-"):
            item = line.lstrip("-").strip()
            if item:
                ladder.append(item)
    if not claim:   # 離線/未依格式 → 退回首行非空當主張（不崩）
        claim = next((l.strip() for l in (text or "").splitlines() if l.strip()), "")
    return CandidateDraft(claim=claim, ladder=ladder, evidence_urls=urls)


class FieldChat:
    """編排：組 messages（system 場脈絡＋歷史＋user）→ chat_backend；蒸餾冊封候選。"""

    def __init__(self, chat_backend: ChatBackend) -> None:
        self.backend = chat_backend

    def reply(self, history: list[dict], user_msg: str, roots) -> str:
        messages = ([{"role": "system", "content": build_field_system_prompt(roots)}]
                    + list(history)
                    + [{"role": "user", "content": user_msg}])
        return self.backend.reply(messages)

    def distill(self, history: list[dict], roots) -> CandidateDraft:
        convo = "\n".join(f"{m.get('role')}：{m.get('content')}" for m in history)
        messages = [{"role": "system", "content": _DISTILL},
                    {"role": "user", "content": convo}]
        return _parse_candidate(self.backend.reply(messages))
