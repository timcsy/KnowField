#!/usr/bin/env python
"""跨 base 判準量測：找出「幾個獨立的知識庫各自撞出同一條」的那些教訓。

⚠️ **沒有校驗就不給群。** 見 SKILL.md——一個沒校驗過的門檻會給你一個
   看起來很專業的錯結論（0.78 ⇒「幾乎沒有複利」），而那不是空結果，是錯結果。
"""
from __future__ import annotations

import argparse
import json
from operator import mul
import pathlib
import re
import sys


def find_bases(roots: list[str]) -> dict[str, pathlib.Path]:
    """每個含 `knowledge/.knowie.json` 的目錄 ＝ 一個 base；名字用專案資料夾名。"""
    out: dict[str, pathlib.Path] = {}
    for root in roots:
        for cfg in sorted(pathlib.Path(root).expanduser().glob("*/knowledge/.knowie.json")):
            out[cfg.parent.parent.name] = cfg.parent
    return out


# ⚠️ **借來的標記——「寫」與「讀」共用同一個常數。**
# 這一支同時是產生器（`emit_lesson`）與讀取器（`lessons`）。兩邊各寫一份字串，
# 有一天會不一致，而**不一致不會報錯**：借來的判準被讀成「這個 base 也獨立撞到了」，
# 群數虛增、排序被自己餵大 ⇒ 那就是馬太迴圈。一個常數，兩邊都用。
BORROWED_MARK = "⚠️ **借來的**"


def lessons(base_dir: pathlib.Path) -> list[str]:
    """`experience.md` 的每個 `###` ＝ 一條教訓；標題就是那句判準。

    ⚠️ **借來的不算。** draft §八 的原話：「只算『撞到』，不算『借走』——
    否則推薦餵回計數、計數又餵回推薦，那就是馬太。」
    ⇒ 一條教訓的內文帶 `BORROWED_MARK` ＝ 它是從別的 base 借來的，
    **在這個 base 真的撞到之前不算這個 base 的經驗**，不進跨 base 計數。
    """
    f = base_dir / "experience.md"
    if not f.exists():
        return []
    out, title, body = [], "", []

    def flush():
        if title and BORROWED_MARK not in "\n".join(body):
            out.append(title)

    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            flush()
            t = re.sub(r"[*`#]", "", line[4:]).strip()
            title, body = (t if len(t) >= 6 else ""), []
        elif line.startswith("## "):
            flush()
            title, body = "", []
        else:
            body.append(line)
    flush()
    return out


def emit_lesson(group: dict) -> str:
    """一群 → 可貼進新 base `experience.md` 的區塊。

    ⚠️ 格式不是排版問題：標記寫壞了，下一次量測就把它算成獨立撞到，
    **而沒有人會發現**。所以由這裡產生，不由人手打。
    """
    bases = sorted({m["base"] for m in group["members"]})
    lines = [f"### {group['claim']}", "",
             f"- {BORROWED_MARK}（`from: {', '.join(bases)}`）"
             f"——**在這個專案真的撞到之前，它不算這個專案的經驗**。",
             "- **各自撞到的原文**："]
    lines += [f"  - `{m['base']}` {m['text']}" for m in group["members"]]
    lines += ["- **來源**：借自個人場的跨 base 量測（`knowie-xbase`）。",
              "  ⇒ **這個 base 真的撞到之後**：刪掉上面那整行、換成這裡的實際出處"
              "（commit／history），它才開始算這個 base 的經驗。", ""]
    block = "\n".join(lines)
    # ⚠️ **標記只能出現一次。** 出現兩次的話，照說明刪掉標記行的人升格會失敗——
    #    另一處還在，量測照樣跳過它，而**沒有人會發現**。這一行擋住那個。
    assert block.count(BORROWED_MARK) == 1, "借來的標記在一個區塊裡只能出現一次"
    return block


# ⚠️ 向量已 L2 正規化（`OpenAIEmbedder` 保證）⇒ 餘弦就是點積，不用再開根號。
# ⚠️ 這裡是 O(n²·d)＝十億次乘法級別，**純 Python 沒有 numpy**：
#    `map(mul, ...)` 比 genexp 快約三倍，這一刀就是靠它跑得完。
def cos(a: list[float], b: list[float]) -> float:
    return fsum_dot(a, b)


def fsum_dot(a: list[float], b: list[float]) -> float:
    return sum(map(mul, a, b))


def embed(texts: list[str]) -> list[list[float]]:
    from knowfield.backends.factory import make_embedder
    from knowfield.config import Config
    cfg = Config.from_env()      # ⚠️ Config() 不讀 .env ⇒ 一定掉回離線 stub
    emb = make_embedder(cfg)
    # ⚠️ 離線 stub 會給你 256 維的雜湊向量——它**會跑完、不會報錯**，
    #    然後所有相似度都是噪音。這裡擋掉，因為那正是「量了一件錯的事」。
    if type(emb).__name__ != "OpenAIEmbedder":
        sys.exit("⚠️ 沒有 OpenAI 相容後端（KNOWFIELD_BACKEND/API key）——"
                 "離線 stub 的相似度是噪音，拒絕給你結果。")
    return emb.embed_many(texts)      # ⚠️ 一條一條打＝1,348 次 API 往返，跑不完


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+", help="放專案的目錄（會找底下的 */knowledge/.knowie.json）")
    ap.add_argument("--calib", action="append", default=[],
                    help='校驗配對 "甲句|||乙句"——你**知道**它們是同一條。至少一組。')
    ap.add_argument("--threshold", type=float, default=0.0, help="校驗完之後才填")
    ap.add_argument("--min-bases", type=int, default=2)
    ap.add_argument("--exclude", action="append", default=[],
                    help="排除某個 base（`knowie-pull` 用：問「**別人**獨立撞到什麼」）")
    ap.add_argument("--emit", default="", help="另外輸出可貼進 experience.md 的區塊")
    ap.add_argument("--top", type=int, default=0, help="只留前 N 群（冷啟動建議 10–15）")
    ap.add_argument("--out", default="")
    ap.add_argument("--cache", default="", help="向量快取（換門檻重跑時免得再打一次 API）")
    a = ap.parse_args()

    bases = find_bases(a.roots)
    for x in a.exclude:
        bases.pop(x, None)
    items = [(b, t) for b, d in bases.items() for t in lessons(d)]
    if len(items) < 2:
        sys.exit(f"只找到 {len(items)} 條教訓——{len(bases)} 個 base。")
    print(f"{len(bases)} 個 base、{len(items)} 條教訓：{', '.join(bases)}", file=sys.stderr)

    texts = [t for _, t in items]
    calib_pairs = [c.split("|||") for c in a.calib if "|||" in c]
    allt = texts + [s for p in calib_pairs for s in p]
    cache = pathlib.Path(a.cache) if a.cache else None
    vecs = None
    if cache and cache.exists():
        c = json.loads(cache.read_text())
        if c.get("texts") == allt:          # ⚠️ 對得上才用——不然是拿舊向量配新句子
            vecs = c["vecs"]
            print(f"用快取 {cache}", file=sys.stderr)
    if vecs is None:
        vecs = embed(allt)
        if cache:
            cache.write_text(json.dumps({"texts": allt, "vecs": vecs}))
    V, cv = vecs[:len(texts)], vecs[len(texts):]

    # ── 噪音帶：跨 base 的隨機配對長什麼樣（不用亂數，取固定跨距的樣本）──
    xs = [cos(V[i], V[j]) for i in range(0, len(V), 7)
          for j in range(i + 1, len(V), 11) if items[i][0] != items[j][0]][:4000]
    xs.sort()
    lo, hi = xs[int(len(xs) * .50)], xs[int(len(xs) * .999)]
    print(f"噪音帶（跨 base 隨機配對）：中位 {lo:.3f}／99.9 分位 {hi:.3f}", file=sys.stderr)

    if not calib_pairs:
        sys.exit("⚠️ 沒有 --calib：沒有已知答案就不知道門檻該落在哪，拒絕給你群。")
    scores = [cos(cv[2 * i], cv[2 * i + 1]) for i in range(len(calib_pairs))]
    for (x, y), s in zip(calib_pairs, scores):
        print(f"校驗 {s:.3f}  {x[:24]}… ↔ {y[:24]}…", file=sys.stderr)
    floor = min(scores)
    if floor <= hi:
        print(f"⚠️ 校驗分數 {floor:.3f} 沒有明顯高過噪音上緣 {hi:.3f}"
              "——換 embedding 模型，或你的校驗配對其實不是同一條。", file=sys.stderr)
    sug = round((floor + hi) / 2, 2)
    # ⚠️ **這個建議只是下界，不是答案。** 校驗配對告訴你門檻不能高過多少（不然真的會漏），
    #    但**沒有**告訴你不能低到多少——連通分量會傳遞性串連，
    #    低一點點就把好幾群黏成一坨（實測 0.59 → 一群 178 條；0.62 → 20 條）。
    #    ⇒ 兩個門檻都跑，看「最大一群」那行，取**不黏**的最高值。
    print(f"⇒ 從 ≈{sug} 起跳，往上試到 {floor:.2f}；每次看「最大一群」那行"
          "——它黏成一坨就是太鬆了", file=sys.stderr)
    if a.threshold <= 0:
        sys.exit("看過上面的數字，再帶 --threshold 跑一次。")

    # ── 分群：只連跨 base 的邊，連通分量 ──
    parent = list(range(len(V)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    th = a.threshold
    for i in range(len(V)):
        vi, bi = V[i], items[i][0]
        for j in range(i + 1, len(V)):
            if items[j][0] != bi and sum(map(mul, vi, V[j])) >= th:
                parent[find(i)] = find(j)
        if i % 200 == 0:
            print(f"  比對 {i}/{len(V)}", file=sys.stderr)
    groups: dict[int, list[int]] = {}
    for i in range(len(V)):
        groups.setdefault(find(i), []).append(i)

    out = []
    for idxs in groups.values():
        bs = {items[i][0] for i in idxs}
        if len(bs) < a.min_bases:
            continue
        # ⚠️ 代表句取**最長**的那條，不是合成的——合併成自己的話是人的事。
        rep = max((items[i][1] for i in idxs), key=len)
        out.append({"claim": rep,
                    "members": [{"base": items[i][0], "text": items[i][1]} for i in sorted(idxs)]})
    out.sort(key=lambda g: -len({m["base"] for m in g["members"]}))
    if a.top:
        # ⚠️ 冷啟動要**少**：knowie 說「保持少數高質量吸引子」。
        #    一次倒一百條，長出來的是「看起來很有經驗、但沒有一條是自己撞出來的」知識庫。
        print(f"⚠️ 只留前 {a.top} 群（共 {len(out)} 群）——冷啟動要少，不是全部", file=sys.stderr)
        out = out[:a.top]
    # ⚠️ 連通分量會**傳遞性串連**：一條假邊就把兩群併成一坨。
    #    最大群的大小就是那個警訊——它比群數更早告訴你門檻放太鬆。
    if out:
        big = max(out, key=lambda g: len(g["members"]))
        print(f"最大一群：{len(big['members'])} 條／{len({m['base'] for m in big['members']})} 個 base"
              f"（>15 條通常代表門檻太鬆，被串起來了）", file=sys.stderr)
    print(f"跨 ≥{a.min_bases} 個 base：{len(out)} 群／{sum(len(g['members']) for g in out)} 條",
          file=sys.stderr)
    if a.emit:
        pathlib.Path(a.emit).write_text("\n".join(emit_lesson(g) for g in out), encoding="utf-8")
        print(f"可貼的區塊寫到 {a.emit}", file=sys.stderr)
    body = json.dumps({"groups": out}, ensure_ascii=False, indent=2)
    if a.out:
        pathlib.Path(a.out).write_text(body, encoding="utf-8")
        print(f"寫到 {a.out}", file=sys.stderr)
    else:
        print(body)


if __name__ == "__main__":
    main()
