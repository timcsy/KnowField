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

import hashlib
import logging
import queue
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from . import protect

_log = logging.getLogger(__name__)

Backend = Callable[[str], str]



def content_key(md: str) -> str:
    """原文內容的 SHA-256（spec 039）。快取以**內容**判新舊，不用時間戳——
    編修內容不一定動時間戳，而 SC-004 要求「0% 機率拿到舊譯文」。

    ⚠️ 呼叫端必須餵**與丟給翻譯器完全相同的那個字串**，否則會出現
    「雜湊算的跟翻的不是同一份」這種沉默錯誤。
    """
    return hashlib.sha256(md.encode("utf-8")).hexdigest()


def split_units(md: str, target: int = 600) -> tuple[list[str], list[str]]:
    """把整篇 markdown 切成**翻譯單位**，回 `(units, seps)`；
    `units[0] + seps[0] + units[1] + …` 逐字等於 `md`。

    ⚠️ **為什麼不重用 `chunk_markdown`**：那是為**檢索**切的，會從單字中間切開
    （實測 Lil'Log 那篇 124 個接縫有 55 個是）。對 embedding 無害，對翻譯致命——
    `Conditioned Generat` ＋ `ion` 各自獨立翻譯，後者變成「離子」。
    **切塊的用途決定了合法的切點；換了用途就得重切。**

    切點優先在段落邊界（空行）；單一段落超過 target 時退而切在空白處，
    **絕不從單字中間切**。
    """
    if not md:
        return [], []
    parts = re.split(r"(\n\s*\n)", md)      # 偶數 index＝區塊、奇數＝分隔（保留以便逐字重組）
    tokens: list[list[str]] = []              # [text, sep_after]
    for i in range(0, len(parts), 2):
        blk = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        subs, subseps = ([blk], []) if (len(blk) <= target or " " not in blk) \
            else _split_on_space(blk, target)
        for j, piece in enumerate(subs):
            tokens.append([piece, subseps[j] if j < len(subseps) else sep])
    # 尾端空區塊（md 以空行結尾）→ 把它的分隔併回前一個單位，別產生空單位
    while len(tokens) > 1 and not tokens[-1][0]:
        tokens[-2][1] += tokens[-1][1]
        tokens.pop()
    # ⚠️ target 要**雙向**作用：上面切開過大的，這裡合併過小的。
    # 只切不合的話，清單項（「- 簡化」）會每個自成一單位——真實語料上
    # 125 塊變成 211 單位，API 呼叫數暴增、耗時從 93s 變 137s，打破 SC-002。
    merged: list[list[str]] = []
    for text, sep in tokens:
        if merged and len(merged[-1][0]) + len(merged[-1][1]) + len(text) <= target:
            merged[-1][0] += merged[-1][1] + text     # 分隔併進文字，逐字還原不受影響
            merged[-1][1] = sep
        else:
            merged.append([text, sep])
    units = [t for t, _ in merged]
    seps = [s for _, s in merged[:-1]]
    units[-1] = units[-1] + merged[-1][1]     # 最後一個分隔沒有後繼 → 併進文字
    return units, seps


def _split_on_space(blk: str, target: int) -> tuple[list[str], list[str]]:
    """過長的單一段落切在空白處；那個空白就是分隔，重組逐字還原。"""
    out: list[str] = []
    seps: list[str] = []
    cur = blk
    while len(cur) > target:
        cut = cur.rfind(" ", 0, target)
        if cut <= 0:
            break
        out.append(cur[:cut])
        seps.append(" ")
        cur = cur[cut + 1:]
    out.append(cur)
    return out, seps


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
        yield ("done", {"chunks": [], "ok": [], "total": 0, "failed": 0})
        return
    if backend is None:
        yield ("stage", {"done": total, "total": total, "failed": total})
        yield ("done", {"chunks": list(chunks), "ok": [False] * total,
                        "total": total, "failed": total})
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
    # `ok` 逐塊回報成敗（spec 039）：呼叫端要據此決定哪些單位**可以**落庫。
    # 用「譯文 == 原文」去猜是猜不準的——純程式碼／URL 的單位翻完本來就可能一樣。
    yield ("done", {"chunks": [r.text for r in results if r is not None],
                    "ok": [bool(r and r.ok) for r in results],
                    "total": total, "failed": failed})
