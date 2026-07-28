"""反逢迎的「值不值得」副手（spec 021）：撒網獵心得 → 反逢迎綜合。

時刻 A——使用者看到新 AI 東西，當場要「真實用戶心得＋值不值得＋怎麼用」。普通 chat AI 最弱
（太新、沒真實心得）。串既有零件、核心零新相依：可插拔 `WebSearch`（spec 009/016）＋ LLM `_post`。

比 SmartSearch 更輕（手動探針證明）：心得證據就在**搜尋結果的標題/摘要**裡——**不逐則抓內文、
不嵌入排序**。獵心得 query 用確定性模板（離線可測、query 品質穩）；價值在**反逢迎綜合** prompt：
官方/獨立/用戶分開、明說炒作/缺點、只依證據＋附引用、沒料說沒料（grounded，原則 3/教訓 7）。
產物短暫、不落庫（原則 5）。搜尋/綜合失敗攔成友善（教訓 3）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..backends.openai_api import OpenAIError, _post
from .websearch import SearchResult


def worthit_queries(subject: str) -> list[str]:
    """獵心得多角度查詢（確定性、非查通用名）：心得/評價、review、缺點、值得嗎、怎麼用。"""
    s = (subject or "").strip()
    if not s:
        return []
    return [
        f"{s} 評價 心得",
        f"{s} review reddit",
        f"{s} 缺點 complaints limitations",
        f"{s} 值得嗎 worth it",
        f"{s} 怎麼用 how to use",
    ]


@dataclass
class WorthItVerdict:
    """一次「值不值得」評估的短暫產出（不落庫）。"""

    subject: str
    verdict_md: str = ""
    sources: list[SearchResult] = field(default_factory=list)
    no_material: bool = False


class WorthItSynthesizer(Protocol):
    def synthesize(self, subject: str, evidence: list[SearchResult]) -> str: ...


class StubWorthItSynthesizer:
    """離線確定性反逢迎綜合：引用 evidence 的 url，零外部呼叫。"""

    def synthesize(self, subject: str, evidence: list[SearchResult]) -> str:
        urls = "、".join(r.url for r in evidence if r.url)
        return (
            f"（離線示意）關於「{subject}」的反逢迎綜合——設定搜尋與 LLM 金鑰後啟用真實撒網心得。\n\n"
            f"**官方說法**：（離線示意，待真實後端）\n"
            f"**獨立評測**：（離線示意）\n"
            f"**真實用戶心得**：（離線示意）\n\n"
            f"**值不值得你**：離線示意，無法給真實裁決。\n"
            f"參考來源：{urls}"
        )


class OpenAIWorthItSynthesizer:
    """OpenAI 格式 chat 產反逢迎綜合。`poster` 可注入供測試。"""

    _SYSTEM = (
        "你是一個『反逢迎』的科技顧問，幫使用者判斷一個新 AI 產品/功能值不值得採用。"
        "只根據提供的搜尋證據作答，繁體中文。務必：\n"
        "1. 把來源分三層寫：**官方說法**、**獨立評測**、**真實用戶心得**——不要混為一談。\n"
        "2. 明確標出『炒作、缺點、難搞、被廣泛抱怨』之處，不要粉飾、不要順著行銷。\n"
        "3. 每個論點盡量附上證據的來源網址可回核；某一層若證據不足，直接說『沒搜到』，"
        "絕不杜撰內容或連結。\n"
        "4. 最後給『值不值得你 follow』的誠實裁決，並可附『怎麼用才發揮』。"
    )

    def __init__(self, base_url: str, api_key: str, model: str, poster=_post) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._poster = poster

    def synthesize(self, subject: str, evidence: list[SearchResult]) -> str:
        ev = "\n".join(
            f"- {r.title}｜{r.url}｜{r.snippet}" for r in evidence) or "（無搜尋結果）"
        user = f"待判物：{subject}\n\n以下是撒網搜到的證據（標題｜網址｜摘要）：\n{ev}"
        try:
            data = self._poster(self.base_url, "/chat/completions", self.api_key, {
                "model": self.model,
                "max_tokens": 900,
                "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": self._SYSTEM},
                    {"role": "user", "content": user},
                ],
            })
            return (data["choices"][0]["message"]["content"] or "").strip()
        except OpenAIError:
            raise
        except Exception as e:  # noqa: BLE001 - 邊界統一成友善的 OpenAIError（教訓 3）
            raise OpenAIError(f"值不值得綜合失敗：{e}") from e


def assess_worth(web_search, synthesizer: WorthItSynthesizer, subject: str, *,
                 result_cap: int = 12) -> WorthItVerdict:
    """撒網獵心得 → 去重 → 反逢迎綜合。搜尋全失敗拋 SourceUnavailable（路由攔）。不落庫。"""
    subject = (subject or "").strip()
    queries = worthit_queries(subject)
    seen: set[str] = set()
    evidence: list[SearchResult] = []
    for q in queries:
        for r in web_search.search(q, news=False):   # 可能拋 SourceUnavailable
            key = (r.url or "").strip() or r.title
            if not key or key in seen:
                continue
            seen.add(key)
            evidence.append(r)
            if len(evidence) >= result_cap:
                break
        if len(evidence) >= result_cap:
            break
    if not evidence:
        return WorthItVerdict(subject=subject, no_material=True)
    return WorthItVerdict(subject=subject,
                          verdict_md=synthesizer.synthesize(subject, evidence),
                          sources=evidence)
