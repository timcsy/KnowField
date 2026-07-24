"""可插拔查詢擴展（spec 011）：把 query 拆成多個貼題子角度，供「深入探索」fan-out。

離線 `StubQueryExpander`（確定性、零外部呼叫、可測）；真實 `OpenAIQueryExpander` 走既有
OpenAI 格式 chat（`_post`，不加 pip 相依）。拆解失敗一律回 `[]`（不拋）——由 SmartSearch
退回單 query（教訓 3）。原 query 由呼叫端保證納入，本類只回「額外角度」。
"""

from __future__ import annotations

import re
from typing import Protocol

from ..backends.openai_api import _post


class QueryExpander(Protocol):
    def expand(self, query: str) -> list[str]: ...


class StubQueryExpander:
    """離線確定性：回三個貼題角度（原理／應用／比較）。零外部呼叫。"""

    def expand(self, query: str) -> list[str]:
        q = (query or "").strip()
        if not q:
            return []
        return [f"{q} 原理", f"{q} 應用", f"{q} 比較"]


def _clean(line: str) -> str:
    # 去掉行首序號（"1." "2)"）與項目符號（- • *）與多餘空白
    return re.sub(r"^\s*(?:\d+[.)、]|[-•*])\s*", "", line).strip()


class OpenAIQueryExpander:
    """OpenAI 格式 chat 拆解 query 成多角度子查詢。`poster` 可注入供測試。"""

    _SYSTEM = (
        "你是搜尋助手。把使用者的問題拆成數個「不同角度、貼題」的子查詢，"
        "涵蓋原理、應用、比較、最新進展等切入點。每行輸出一個子查詢，"
        "只輸出子查詢本身，不要編號、不要解說、不要空行。"
    )

    def __init__(self, base_url: str, api_key: str, model: str,
                 max_n: int = 5, poster=_post) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.max_n = max_n
        self._poster = poster

    def expand(self, query: str) -> list[str]:
        q = (query or "").strip()
        if not q:
            return []
        try:
            data = self._poster(self.base_url, "/chat/completions", self.api_key, {
                "model": self.model,
                "max_tokens": 200,
                "temperature": 0.4,
                "messages": [
                    {"role": "system", "content": self._SYSTEM},
                    {"role": "user", "content": q},
                ],
            })
            content = data["choices"][0]["message"]["content"]
        except Exception:  # noqa: BLE001 - 拆解失敗回 []，由 SmartSearch 退回單 query
            return []
        out: list[str] = []
        for line in (content or "").splitlines():
            s = _clean(line)
            if s and s not in out:
                out.append(s)
            if len(out) >= self.max_n:
                break
        return out
