"""結構化日誌（憲章原則 V：可觀測、錯誤不靜默）。"""

from __future__ import annotations

import json
import logging
import sys


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        # 附掛額外欄位（logger.info(..., extra={"extra": {...}})）
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "knowfield") -> logging.Logger:
    """取一個 logger；handler 一律掛在**套件根** `knowfield` 上，再回傳要的那個子 logger。

    ⚠️ 舊版把 handler 掛在傳進來的名字上（實務上只有 `knowfield.web` 與 `knowfield.cli`），
    於是**沒人呼叫過 get_logger 的模組**——例如 `knowfield.text.translate`——整條鏈上
    找不到 handler，`knowfield` 又是 NOTSET（吃到 root 的 WARNING），INFO 全被丟掉。
    後果是 translate 的「第 N 塊退回原文」在正式執行時**從來沒印出來過**，
    而那正是診斷翻譯降級唯一的線索（2026-08-21 spec 039 真跑時發現）。
    掛在套件根：一次修好所有 `knowfield.*`，且不會有重複行（子 logger 不自帶 handler）。
    """
    root = logging.getLogger("knowfield")
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonFormatter())
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    return logging.getLogger(name)
