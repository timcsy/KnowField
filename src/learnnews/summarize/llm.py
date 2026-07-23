"""摘要 LLM 後端（可插拔，research.md R5）。

`Summarizer` 回傳 (定位, 為何值得看) 兩段短句。MVP 與測試預設 `StubSummarizer`
（確定性、離線）；生產可換 `ClaudeSummarizer`（claude-haiku-4-5）。

無論後端為何，長度與「不代勞」的最終保證由 summarizer.py 的程式端守衛負責
（不依賴模型自律）。
"""

from __future__ import annotations

from typing import Protocol


class Summarizer(Protocol):
    def summarize(self, title: str, abstract: str, matched_topic: str) -> tuple[str, str]:
        ...


class StubSummarizer:
    """確定性摘要：只做「定位＋為何值得看」，不做任何分析或結論。"""

    def summarize(self, title: str, abstract: str, matched_topic: str) -> tuple[str, str]:
        positioning = f"這則談的是「{title.strip()}」"
        if matched_topic:
            why = f"與你關注的「{matched_topic}」相關，值得點進去判斷"
        else:
            why = "落在你的興趣範圍內，值得快速判斷"
        return positioning, why


class ClaudeSummarizer:
    """生產用後端：呼叫 Claude Haiku 產生封頂摘要。

    需安裝 `anthropic` 並設定 ANTHROPIC_API_KEY。提示明令：只給定位與是否值得看，
    禁止任何結論式判斷或深度分析（原則 4）。此類別在 MVP/測試中不使用。
    """

    _PROMPT = (
        "你是新聞分診助手。只用繁體中文，為這則內容產生兩段極短句：\n"
        "1) 一句定位（這則在談什麼）；2) 一句為何值得看。\n"
        "嚴禁做任何結論式判斷、評價或深度分析——你的工作只是幫使用者決定要不要點進去。\n"
        "標題：{title}\n摘要：{abstract}\n關注主題：{topic}\n"
        "輸出格式：第一行定位，第二行為何值得看。"
    )

    def __init__(self, model: str = "claude-haiku-4-5") -> None:
        self.model = model

    def summarize(self, title: str, abstract: str, matched_topic: str) -> tuple[str, str]:  # pragma: no cover
        import anthropic  # 延遲載入，MVP 不強制安裝

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=self.model,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": self._PROMPT.format(
                    title=title, abstract=abstract[:1000], topic=matched_topic
                ),
            }],
        )
        text = msg.content[0].text.strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        positioning = lines[0] if lines else f"這則談的是「{title}」"
        why = lines[1] if len(lines) > 1 else "值得快速判斷"
        return positioning, why
