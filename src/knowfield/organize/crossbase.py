"""跨 base 判準：**幾個獨立的知識庫各自撞出同一條**。

⚠️ **吃資料，不吃路徑。** 教訓從磁碟、從 clone、還是從 `ext_items` 來，這支都不在乎
   ——`knowie-crosscheck` 那版寫死在磁碟上，搬進來時不要重複那個。

⚠️ **沒有校驗配對就不給群。** 一個沒校驗過的門檻會給你一個**看起來很專業的錯結論**：
   第一次用 0.78 得到「幾乎沒有複利」，而拿一對已知同義的句子去量只有 0.617
   ——真門檻在 0.62 附近。差這 0.16，結論從「49 群」變成「沒有」。
"""
from __future__ import annotations

import re
from operator import mul

#: 借來的標記——**產生器與讀取器共用一個常數**。各寫一份字串遲早會不一致，
#: 而不一致不會報錯：借來的判準被讀成「這個 base 也獨立撞到了」⇒ 馬太迴圈。
BORROWED_MARK = "⚠️ **借來的**"

_DIRS = ("concepts", "history", "episodes", "draft", "skills")
_FILES = ("experience", "vision", "principles")

# ⚠️ 各個 base 的**私有記號**不能跟著判準跑到別人那裡去（實測 1,358 條標題：
# `🔴`×356 · `⭐`×102 · `⚠`×48，275 條以它們開頭）。而 `→ ≠ ⇒ ∃ ∀` 是**內容**
# （「批准 ≠ 打到需求」）⇒ **只剝開頭那一串**。失敗方向也對：剝不乾淨只是留一個記號，
# 剝過頭是改掉別人的話。
_LEAD = re.compile(r"^[\U0001F300-\U0001FAFF⬀-⯿⚠✔❌️\s]+")
_HTML = re.compile(r"</?[a-zA-Z][^>]*>")


def clean(title: str) -> str:
    """`### ` 後面那一段 → 可攜的判準句。"""
    return _LEAD.sub("", _HTML.sub("", re.sub(r"[*`#]", "", title))).strip()


def layer_of(path: str) -> str:
    rest = path[len("knowledge/"):] if path.startswith("knowledge/") else path
    head, _, tail = rest.partition("/")
    if tail:
        return head if head in _DIRS else "other"
    stem = head.rsplit(".", 1)[0] if head.endswith(".md") else ""
    return stem if stem in _FILES else "other"


def lessons_from(items: list[dict]) -> list[str]:
    """`[{path, body}]` → 判準句。

    ⚠️ **借來的不算。** draft §八：「只算『撞到』，不算『借走』——否則推薦餵回計數、
    計數又餵回推薦，那就是馬太。」
    ⓘ 概念的**檔名就是主張**（根公理 1：一個概念，多個投影）——概念層撞到比教訓層強。
    """
    out: list[str] = []
    for it in items:
        path, body = it.get("path", ""), it.get("body", "") or ""
        layer = it.get("layer") or layer_of(path)
        if layer == "concepts":
            name = clean(path.rsplit("/", 1)[-1].rsplit(".", 1)[0])
            if len(name) >= 6 and name.upper() != "README":
                out.append(name)
            continue
        if layer != "experience":
            continue
        title, buf = "", []

        def flush():
            if title and BORROWED_MARK not in "\n".join(buf):
                out.append(title)

        for line in body.splitlines():
            if line.startswith("### "):
                flush()
                t = clean(line[4:])
                title, buf = (t if len(t) >= 6 else ""), []
            elif line.startswith("## "):
                flush()
                title, buf = "", []
            else:
                buf.append(line)
        flush()
    return out


def emit_lesson(group: dict) -> str:
    """一群 → 可貼進新 base `experience.md` 的區塊。

    ⚠️ 格式不是排版問題：標記寫壞了，下一次量測就把它算成獨立撞到，**而沒有人會發現**。
    所以由這裡產生、不由人手打——而且它跟 `lessons_from`（讀的那半）**住在同一個檔案**。
    """
    bases = sorted({m["base"] for m in group["members"]})
    lines = [f"### {group['claim']}", "",
             f"- {BORROWED_MARK}（`from: {', '.join(bases)}`）"
             f"——**在這個專案真的撞到之前，它不算這個專案的經驗**。",
             "- **各自撞到的原文**："]
    lines += [f"  - `{m['base']}` {m['text']}" for m in group["members"]]
    lines += ["- **來源**：借自個人場的跨 base 量測。",
              "  ⇒ **這個 base 真的撞到之後**：刪掉上面那整行、換成這裡的實際出處"
              "（commit／history），它才開始算這個 base 的經驗。", ""]
    block = "\n".join(lines)
    # ⚠️ **標記只能出現一次。** 出現兩次的話，照說明刪掉標記行的人升格會失敗——
    #    另一處還在，量測照樣跳過它，而**沒有人會發現**。
    assert block.count(BORROWED_MARK) == 1, "借來的標記在一個區塊裡只能出現一次"
    return block


def _dot(a, b):
    return sum(map(mul, a, b))          # 向量已 L2 正規化 ⇒ 餘弦就是點積


def calibrate(vec: dict, items: list[tuple[str, str]], pairs: list[tuple[str, str]]) -> dict:
    """回**兩個界**，不是一個數字。

    ⚠️ 校驗配對只回答「不能再高」；「不能再低」由**結構崩壞**守著——連通分量會傳遞性
    串連（A≈B、B≈C ⇒ A 和 C 同群，即使它們不像）。只量一邊會拿到一個**有校驗背書的錯數字**，
    比沒校驗更難懷疑。實測：建議值 0.59 產生一群 178 條；0.62 最大群 20。
    """
    xs = sorted(_dot(vec[items[i][1]], vec[items[j][1]])
                for i in range(0, len(items), 7)
                for j in range(i + 1, len(items), 11)
                if items[i][0] != items[j][0])[:4000]
    noise_hi = xs[int(len(xs) * .999)] if xs else 0.0
    scores = [_dot(vec[a], vec[b]) for a, b in pairs if a in vec and b in vec]
    return {"noise_median": xs[len(xs) // 2] if xs else 0.0, "noise_hi": noise_hi,
            "calibration": scores, "floor": min(scores) if scores else 0.0}


def group(bases: dict[str, list[str]], vec: dict, threshold: float,
          min_bases: int = 2, top: int = 0) -> dict:
    """跨 base 分群（連通分量）。回 `{groups, largest, n_groups}`。

    ⚠️ `largest` 一定要回——**它就是門檻的下界訊號**：黏成一坨就是太鬆了。
    """
    items = [(b, t) for b, ts in bases.items() for t in ts if t in vec]
    n = len(items)
    par = list(range(n))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i

    for i in range(n):
        vi, bi = vec[items[i][1]], items[i][0]
        for j in range(i + 1, n):
            if items[j][0] != bi and _dot(vi, vec[items[j][1]]) >= threshold:
                par[find(i)] = find(j)
    buckets: dict[int, list[int]] = {}
    for i in range(n):
        buckets.setdefault(find(i), []).append(i)

    out = []
    for idxs in buckets.values():
        bs = {items[i][0] for i in idxs}
        if len(bs) < min_bases:
            continue
        # ⚠️ 代表句取**最長**的那條，不合成——合併成自己的話是**人**的事（冊封時可改）
        rep = max((items[i][1] for i in idxs), key=len)
        out.append({"claim": rep,
                    "members": [{"base": items[i][0], "text": items[i][1]}
                                for i in sorted(idxs)]})
    out.sort(key=lambda g: (-len({m["base"] for m in g["members"]}), -len(g["members"])))
    largest = max((len(g["members"]) for g in out), default=0)
    return {"groups": out[:top] if top else out, "n_groups": len(out), "largest": largest}
