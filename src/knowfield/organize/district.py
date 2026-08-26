"""spec 069：行政區——領域改成機器劃、人核准。

**邊界是資料，不是函數**：存的是「指派」（誰在哪一區），不是「離誰最近」。
⇒ 換 embedding 模型不會重劃；新增一個區不會讓別的區靜靜改變。

⚠️ **這裡只處理「還沒有地址」的東西。** 實驗（117 節點）量到換個隨機種子分區就大幅重排
（ARI ≈ 0.18）⇒ 全量重劃會讓大量地址改變。所以那個禁令做在**結構上**：
沒有一條路可以碰到已經歸屬的東西——不是靠記得不要。
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

_NAME = (
    "下面是一群知識的共同錨（一條理解）與幾個成員。給這一群一個**資料夾名字**。\n"
    "規則：\n"
    "- 2–8 個字、名詞、看得懂。\n"
    "- **要用成員文字裡真的出現過的詞**，不要自己造抽象詞。\n"
    "- **不要用一個可以套在任何一群上的字**（「AI」「模型」「系統」「方法」「技術」）。\n"
    "  判準：這個名字**排除掉了什麼**？答不出來就換一個更具體的。\n"
    "只輸出那個名字，不要別的字。"
)
#: ⚠️ 泛詞黑名單。LLM 最省力的答案永遠是「共有的最泛的詞」，而那種名字沒有修剪力
#: ——這是分群命名的經典退化，光在 prompt 裡講不夠，要擋。
_TOO_GENERIC = {"AI", "ai", "模型", "系統", "方法", "技術", "知識", "資料", "學習",
                "研究", "筆記", "其他", "雜項", "LLM", "llm"}


def _norm(v):
    s = math.sqrt(sum(a * a for a in v)) or 1.0
    return [a / s for a in v]


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cen(vs):
    n = len(vs[0])
    c = [0.0] * n
    for v in vs:
        for i, a in enumerate(v):
            c[i] += a
    return [a / len(vs) for a in c]


def _positions(repo, embedder) -> tuple[dict, dict, dict]:
    """未歸屬東西的位置。回 (pos, label, kind)。

    ⚠️ 互動用**它冊封出的理解的重心**、應用用**骨幹理解的重心**——
    這不只是省一次 API：**互動的位置由它產出的理解決定**，
    比拿標題去 embed 更貼近它實際在講什麼。
    """
    import json as _json
    unfiled = [r for r in repo._inventory_rows() if r.get("domain_id") is None]
    label = {(r["kind"], r["ref"]): (r.get("label") or str(r["ref"])) for r in unfiled}
    keys = list(label)
    if embedder is None:
        return {}, label, {}

    tag = getattr(embedder, "tag", None) or "openai-text-embedding-3-small"
    vec: dict = {}
    for x in repo.conn.execute("SELECT entry_id, vector_json FROM entry_embeddings"
                               " WHERE tag=%s", (tag,)).fetchall():
        vec[int(x["entry_id"])] = _json.loads(x["vector_json"])

    pos: dict = {}
    for k in keys:
        if k[0] == "why_node" and -int(k[1]) in vec:
            pos[k] = vec[-int(k[1])]
    chunks = defaultdict(list)
    for x in repo.conn.execute("SELECT id, url FROM digest_entries").fetchall():
        if int(x["id"]) in vec:
            chunks[x["url"]].append(vec[int(x["id"])])
    for k in keys:
        if k[0] == "source" and k[1] in chunks:
            pos[k] = _cen(chunks[k[1]])
    cw, aw = defaultdict(list), defaultdict(list)
    for x in repo.conn.execute("SELECT id, conversation_id FROM why_nodes"
                               " WHERE conversation_id IS NOT NULL").fetchall():
        if -int(x["id"]) in vec:
            cw[int(x["conversation_id"])].append(vec[-int(x["id"])])
    for x in repo.conn.execute("SELECT article_id, why_node_id FROM article_roots").fetchall():
        if -int(x["why_node_id"]) in vec:
            aw[int(x["article_id"])].append(vec[-int(x["why_node_id"])])
    for k in keys:
        if k[0] == "conversation" and int(k[1]) in cw:
            pos[k] = _cen(cw[int(k[1])])
        elif k[0] == "article" and int(k[1]) in aw:
            pos[k] = _cen(aw[int(k[1])])

    missing = [k for k in keys if k not in pos]
    if missing:
        texts = [label[k][:400] for k in missing]
        try:
            vs = (embedder.embed_many(texts) if hasattr(embedder, "embed_many")
                  else [embedder.embed(t) for t in texts])
            for k, v in zip(missing, vs):
                pos[k] = v
        except Exception:  # noqa: BLE001 - 補算失敗就少幾件，不該炸
            pass
    # ⚠️ 維度不一致就整個放棄——把 256 維的 stub 混進 1536 維的真實向量，
    #    結果會是**看起來正常的垃圾**（實驗時真的差點發生）。
    dims = Counter(len(v) for v in pos.values())
    if len(dims) > 1:
        return {}, label, {}
    return {k: _norm(v) for k, v in pos.items()}, label, {}


def _edges(repo, present: set) -> list[tuple]:
    """真實的關係（道路）。⚠️ 權重高於相似度——人建立的連結比「像」更可信，
    而且它讓相似度**不是單點故障**。"""
    out = []
    u = {int(x["id"]): x["url"] for x in
         repo.conn.execute("SELECT id, url FROM digest_entries").fetchall()}
    for x in repo.conn.execute("SELECT id, conversation_id, source_entry_id"
                               " FROM why_nodes").fetchall():
        w = ("why_node", int(x["id"]))
        if w not in present:
            continue
        c = ("conversation", int(x["conversation_id"] or 0))
        if x["conversation_id"] and c in present:
            out.append((w, c, 2.0))
        sid = int(x["source_entry_id"] or 0)
        if sid and u.get(sid) and ("source", u[sid]) in present:
            out.append((w, ("source", u[sid]), 2.0))
    for x in repo.conn.execute("SELECT id, carried_ref FROM conversations"
                               " WHERE carried_kind='source'").fetchall():
        c, s = ("conversation", int(x["id"])), ("source", x["carried_ref"])
        if c in present and s in present:
            out.append((c, s, 2.0))
    for x in repo.conn.execute("SELECT article_id, why_node_id FROM article_roots").fetchall():
        a, w = ("article", int(x["article_id"])), ("why_node", int(x["why_node_id"]))
        if a in present and w in present:
            out.append((a, w, 2.0))
    return out


def _partition(nodes, P, adj, k, cap):
    """平衡分割：人口是**約束**不是目標（目標是最小化切斷的邊）。"""
    seeds = [nodes[0]]
    while len(seeds) < k:
        d = {n: min(1 - _cos(P[n], P[s]) for s in seeds) for n in nodes}
        seeds.append(max(d, key=d.get))
    C = [P[s][:] for s in seeds]
    assign: dict = {}
    for _ in range(10):
        cand = sorted((1 - _cos(P[n], C[i]), str(n), n, i)
                      for n in nodes for i in range(k))
        assign, cnt = {}, [0] * k
        for _d, _s, n, i in cand:
            if n in assign or cnt[i] >= cap:
                continue
            assign[n] = i
            cnt[i] += 1
        for n in nodes:
            if n not in assign:
                i = min(range(k), key=lambda j: (cnt[j], 1 - _cos(P[n], C[j])))
                assign[n] = i
                cnt[i] += 1
        NC = []
        for i in range(k):
            ms = [P[n] for n in nodes if assign[n] == i]
            NC.append(_norm(_cen(ms)) if ms else C[i])
        C = NC
    for _ in range(5):                       # 邊感知微調
        moved, cnt = 0, Counter(assign.values())
        for n in nodes:
            cur = assign[n]
            g: dict = defaultdict(float)
            for nb, w in adj[n].items():
                g[assign[nb]] += w
            if not g:
                continue
            best = max(g, key=g.get)
            if best != cur and g[best] > g[cur] + 0.5 and cnt[best] < cap:
                assign[n] = best
                cnt[best] += 1
                cnt[cur] -= 1
                moved += 1
        if not moved:
            break
    return assign, C


def districts(repo, embedder, k: int | None = None, chat=None) -> list[dict]:
    """把**還沒有地址**的東西劃成幾個區。回跟 spec 065 一樣形狀的建議夾。

    ⚠️ 沒有向量時退回既有的邊分群（spec 065）——**不是回空的**：
    回空的會讓使用者以為「沒東西可整理」，那是把故障畫成結論。
    """
    pos, label, _ = _positions(repo, embedder)
    if len(pos) < 4:
        from .suggest import suggest_folders
        return [f for f in suggest_folders(repo, chat or _Dead()) if not f.get("lonely")]

    nodes = sorted(pos, key=str)
    present = set(nodes)
    edges = _edges(repo, present)
    adj: dict = defaultdict(lambda: defaultdict(float))
    for a, b, w in edges:
        adj[a][b] += w
        adj[b][a] += w
    for kind in {n[0] for n in nodes}:
        ks = [n for n in nodes if n[0] == kind]
        for a in ks:                        # 同種＝相似度（地形）
            for s, b in sorted(((_cos(pos[a], pos[b]), str(b)) for b in ks if b != a),
                               reverse=True)[:6]:
                if s > 0.3:
                    b2 = next(x for x in ks if str(x) == b)
                    adj[a][b2] += float(s)
                    adj[b2][a] += float(s)

    k = k or max(2, min(7, round(len(nodes) / 18) or 2))
    cap = math.ceil(len(nodes) / k) + 3
    assign, C = _partition(nodes, pos, adj, k, cap)

    out = []
    for i in range(k):
        mem = [n for n in nodes if assign[n] == i]
        if not mem:
            continue
        near = sorted(mem, key=lambda n: 1 - _cos(pos[n], C[i]))
        whys = [n for n in near if n[0] == "why_node"]
        anchor = whys[0] if whys else near[0]
        out.append({
            "name": _short_name(label[anchor], [label[n] for n in near[:4]], chat),
            "parent": "", "anchor": {"kind": anchor[0], "ref": anchor[1]},
            # ⚠️ 理由要**可判斷**：列錨與代表成員，你能說「不對，這些跟那條沒關係」。
            #    分數（0.87）不是理由——它不可反駁。
            "reasons": [f"這 {len(mem)} 件都最靠近〈{label[anchor][:34]}〉",
                        "最靠近中心的幾件：" + "、".join(label[n][:18] for n in near[1:4])],
            "edges": [],
            "items": [{"kind": n[0], "ref": n[1], "label": label[n]} for n in mem],
            "count": len(mem), "suggest_apply": True,
        })
    return out


class _Dead:
    def reply(self, messages):
        raise RuntimeError("沒有 LLM")


def _short_name(anchor_label: str, samples: list[str], chat) -> str:
    """區名。⚠️ 錨是那條理解（穩定、可查證），但**顯示名要短**——
    實驗印出的區名是一整句主張，完全不能當資料夾名。"""
    if chat is not None:
        try:
            body = f"錨：{anchor_label[:200]}\n成員：" + "、".join(s[:40] for s in samples)
            got = (chat.reply([{"role": "system", "content": _NAME},
                               {"role": "user", "content": body}]) or "").strip()
            got = got.splitlines()[0].strip().strip("「」\"'")
            # ⚠️ 泛詞擋掉，退回錨——一個沒有修剪力的名字比一句長主張更糟：
            #    長主張至少告訴你這一區在講什麼。
            if 1 < len(got) <= 20 and got not in _TOO_GENERIC:
                return got
        except Exception:  # noqa: BLE001 - 命名失敗不該擋住劃界
            pass
    return anchor_label[:16]
