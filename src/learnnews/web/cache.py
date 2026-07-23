"""即時拉的記憶體 TTL 快取（FR-005／SC-004）。本機單人足夠，YAGNI。

避免重複主題狂打真實後端。`now` 可注入以利測試（不依賴真實時鐘）。
"""

from __future__ import annotations

from typing import Callable


def normalize_topic(topic: str) -> str:
    return " ".join((topic or "").strip().lower().split())


class TTLCache:
    def __init__(self, ttl_seconds: float = 600.0,
                 clock: Callable[[], float] | None = None) -> None:
        self.ttl = ttl_seconds
        self._clock = clock or _default_clock
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, topic: str):
        key = normalize_topic(topic)
        hit = self._store.get(key)
        if hit is None:
            return None
        ts, value = hit
        if self._clock() - ts > self.ttl:
            del self._store[key]        # 過期
            return None
        return value

    def set(self, topic: str, value) -> None:
        self._store[normalize_topic(topic)] = (self._clock(), value)


def _default_clock() -> float:
    import time
    return time.monotonic()
