"""英→繁一鍵全文翻譯的核心（spec 038，階段 34 第二刀）。

**與第一刀（簡→繁）的性質差異**：那是正規化（確定性、零失真），這是**翻譯**
（生成式、必然失真、模型不保證照規則）。所以這裡多了一層第一刀不需要的東西：

    保護片段完整性檢查 —— 缺任何一個佔位符，該塊**整塊退回原文**。

為什麼不修補：`restore` 靠佔位符把承重內容塞回原位，少一個就是那段公式／程式碼
**永久消失**（不是改壞，是不見）。而把它接回結尾會產生位置錯的公式——比沒有翻譯更糟。
⇒ 寧可不翻，不可殘缺。與 spec 037 FR-006「少做比做壞安全」同方向。

LLM 呼叫走**注入的 backend**（`str -> str`），讓上面這些邏輯在零外呼下可測。
"""
from __future__ import annotations

import logging
import queue
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from . import protect

_log = logging.getLogger(__name__)

Backend = Callable[[str], str]


@dataclass(frozen=True)
class TranslatedChunk:
    index: int
    text: str
    ok: bool


def translate_one(chunk: str, backend: Backend, index: int = 0) -> TranslatedChunk:
    """翻一塊。任何問題都降級為原文，不向外拋（單塊失敗不該中斷整篇）。"""
    masked, segments = protect.mask(chunk)
    try:
        out = backend(masked)
    except Exception as exc:  # noqa: BLE001 - 邊界：單塊失敗降級，不中斷其他塊
        _log.info("translate：第 %d 塊後端失敗，退回原文（%s）", index, exc)
        return TranslatedChunk(index, chunk, False)
    # 生成式模型不保證照抄佔位符——缺一個就整塊放棄
    missing = [i for i in range(len(segments)) if protect.placeholder(i) not in out]
    if missing:
        _log.info("translate：第 %d 塊掉了 %d 個保護片段，退回原文", index, len(missing))
        return TranslatedChunk(index, chunk, False)
    return TranslatedChunk(index, protect.restore(out, segments), True)


def translate_chunks(chunks: list[str], backend: Backend | None,
                     max_workers: int = 8,
                     on_progress: Callable[[int, int, int], None] | None = None,
                     ) -> list[TranslatedChunk]:
    """並行翻多塊。塊數與順序與輸入一致。

    形狀沿用 `summarize/article.py` 的 `build_articles`（實測 11.1 分 → 1.8 分，
    見 specs/038 research 決策 1）：`ex.map` 保序、單元素不開池、`min(workers, len)`。

    `backend=None`（不可用）→ 全部原樣回傳，不中斷（FR-010）。
    `on_progress(done, total, failed)` 每完成一塊觸發一次。
    """
    total = len(chunks)
    if not chunks:
        return []
    if backend is None:
        out = [TranslatedChunk(i, c, False) for i, c in enumerate(chunks)]
        if on_progress:
            on_progress(total, total, total)
        return out

    state = {"done": 0, "failed": 0}

    def run(pair: tuple[int, str]) -> TranslatedChunk:
        i, c = pair
        r = translate_one(c, backend, i)
        # ex.map 保序但完成順序不定；計數只用於進度回報，不參與結果排序
        state["done"] += 1
        if not r.ok:
            state["failed"] += 1
        if on_progress:
            on_progress(state["done"], total, state["failed"])
        return r

    pairs = list(enumerate(chunks))
    if total == 1:
        return [run(pairs[0])]
    with ThreadPoolExecutor(max_workers=min(max_workers, total)) as ex:
        return list(ex.map(run, pairs))


def translate_stream(chunks: list[str], backend: Backend | None, max_workers: int = 8):
    """與 `translate_chunks` 同樣的工作，但**邊做邊吐**進度。

    產出 `("stage", {done,total,failed})` … 然後 `("done", {chunks,total,failed})`。

    ⚠️ 為什麼不是在 `translate_chunks` 外面包一層「收集完再吐」：那樣使用者會盯著
    沒反應的畫面等 1.8 分鐘，最後一次看到全部——**是假 spinner，不是進度**
    （experience：「慢操作要給即時進度，而非假 spinner」）。差別在這裡是結構性的，
    不是措辭：進度必須在工作**進行中**離開這個函式。

    HTTP 層只負責把這些事件包成 SSE——串流邏輯留在這裡，才測得到時機。
    """
    total = len(chunks)
    if not chunks:
        yield ("done", {"chunks": [], "total": 0, "failed": 0})
        return
    if backend is None:
        yield ("stage", {"done": total, "total": total, "failed": total})
        yield ("done", {"chunks": list(chunks), "total": total, "failed": total})
        return

    q: queue.Queue = queue.Queue()
    results: list[TranslatedChunk | None] = [None] * total

    def worker(pair):
        i, c = pair
        r = translate_one(c, backend, i)
        results[i] = r
        q.put(r)

    with ThreadPoolExecutor(max_workers=min(max_workers, total)) as ex:
        for pair in enumerate(chunks):
            ex.submit(worker, pair)
        done = failed = 0
        while done < total:
            r = q.get()                      # 一完成就放行，不等其他塊
            done += 1
            if not r.ok:
                failed += 1
            yield ("stage", {"done": done, "total": total, "failed": failed})
    yield ("done", {"chunks": [r.text for r in results if r is not None],
                    "total": total, "failed": failed})
