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


def lessons(base_dir: pathlib.Path) -> list[str]:
    """`experience.md` 的每個 `###` ＝ 一條教訓；標題就是那句判準。"""
    f = base_dir / "experience.md"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            t = re.sub(r"[*`#]", "", line[4:]).strip()
            if len(t) >= 6:
                out.append(t)
    return out


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
    ap.add_argument("--out", default="")
    ap.add_argument("--cache", default="", help="向量快取（換門檻重跑時免得再打一次 API）")
    a = ap.parse_args()

    bases = find_bases(a.roots)
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
    # ⚠️ 連通分量會**傳遞性串連**：一條假邊就把兩群併成一坨。
    #    最大群的大小就是那個警訊——它比群數更早告訴你門檻放太鬆。
    if out:
        big = max(out, key=lambda g: len(g["members"]))
        print(f"最大一群：{len(big['members'])} 條／{len({m['base'] for m in big['members']})} 個 base"
              f"（>15 條通常代表門檻太鬆，被串起來了）", file=sys.stderr)
    print(f"跨 ≥{a.min_bases} 個 base：{len(out)} 群／{sum(len(g['members']) for g in out)} 條",
          file=sys.stderr)
    body = json.dumps({"groups": out}, ensure_ascii=False, indent=2)
    if a.out:
        pathlib.Path(a.out).write_text(body, encoding="utf-8")
        print(f"寫到 {a.out}", file=sys.stderr)
    else:
        print(body)


if __name__ == "__main__":
    main()
