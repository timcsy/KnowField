"""可選 AI 示意圖（spec 003，FR-007）。

無原文圖且使用者以 `--ai-image` 啟用時，可生成示意圖。**產生者一律標 kind="AI 示意"**，
渲染必顯示「AI 示意・非原文」，不得與原文圖混淆（原則 3）。預設關閉；失敗則回 None
（退純文字，不阻塞）。
"""

from __future__ import annotations

from ..backends.openai_api import OpenAIError, _post
from ..config import Config
from ..models import Item
from ..summarize.article import Figure


class StubAIImage:
    """離線占位：回傳標示為 AI 示意的圖（無真實影像，供測試/離線）。"""

    def __call__(self, item: Item) -> Figure | None:
        return Figure(kind="AI 示意", url="(ai-generated placeholder)",
                      source_note="AI 示意・非原文")


class OpenAIAIImage:
    """走 OpenAI 格式 images 端點生成示意圖。失敗回 None（不阻塞）。"""

    def __init__(self, config: Config) -> None:
        self.config = config

    def __call__(self, item: Item) -> Figure | None:
        try:
            data = _post(self.config.api_base_url, "/images/generations",
                         self.config.api_key, {
                             "prompt": f"為這則內容畫一張說明性示意圖：{item.title}",
                             "n": 1, "size": "512x512",
                         })
            url = data["data"][0].get("url", "")
            if not url:
                return None
            return Figure(kind="AI 示意", url=url, source_note="AI 示意・非原文")
        except (OpenAIError, KeyError, IndexError):
            return None
