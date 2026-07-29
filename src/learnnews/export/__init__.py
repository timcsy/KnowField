"""匯出核心（spec 024）：把已沉澱的對話／根因組成 NotebookLM 可吃的格式。

零相依、純函式、離線可測、唯讀——只把場的產物「匯出」，絕不把外物注入回場（原則 6）。
"""

from .notebooklm import (
    conversation_evidence_urls,
    conversation_to_markdown,
    dedup_urls,
    why_node_to_markdown,
)

__all__ = [
    "conversation_to_markdown",
    "conversation_evidence_urls",
    "why_node_to_markdown",
    "dedup_urls",
]
