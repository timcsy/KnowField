"""US1 的預設興趣清單提供者。

讓 US1（每日分診）能在 US2（興趣管理）尚未實作時獨立測試。若使用者已在興趣畫像
設定明講主題，digest 會改用該畫像（見 US2/T041）。
"""

from __future__ import annotations

DEFAULT_TOPICS = [
    "LLM 推理",
    "agent",
    "編譯器",
    "具身智慧",
]


def preset_topics() -> list[str]:
    return list(DEFAULT_TOPICS)
