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
    "你要幫一個知識庫的資料夾取名字。下面是這個庫**所有**分區，每一區列了它的成員。\n"
    "給每一區一個名字。\n"
    "\n"
    "好名字的判準——**兩個方向都要滿足**：\n"
    "- **不能太泛**：如果這個名字套在**別的區**上也說得通，它就沒有用\n"
    "  （「其他」「雜項」這類沒有內容的詞就是這種）。\n"
    "- **不能太窄**：如果**超過三分之一的成員**你會問「這為什麼在這裡」，\n"
    "  那你是在描述其中某一件，不是這一區。\n"
    "\n"
    "其他規則：\n"
    "- 2–10 個字，名詞或名詞短語，看得懂。\n"
    "- 用**成員文字裡真的出現過的詞**去組，不要自己造抽象詞。\n"
    "- 繁體中文；除非那個概念本來就沒有中文說法（Transformer、Flow Matching 這類）。\n"
    "- 各區的名字**必須彼此不同，而且一眼分得出差別**。\n"
    "- 領域術語（「深度學習」「同調論」這種）**可以用**——只要它確實是這一區在講的東西。\n"
    "- 這些成員本來就有點雜，**不必找到完美的名字**：找那個能涵蓋**最多成員**的詞就好。\n"
    "  「未命名」是最後手段，只有在成員之間**真的沒有共同點**時才用。\n"
    "\n"
    "每行一個，格式：\n"
    "`<區id>｜<名字>｜<它跟哪幾區最容易被搞混，而這個名字怎麼把它們分開>`\n"
    "第三欄是**寫給人看的**，一句話就好；用「未命名」時，第三欄要說**為什麼取不出來**。\n"
    "只輸出這些行，不要別的字。"
)

#: ⚠️ **不擋名字。**
#:
#: 我加過兩層過濾：一張泛詞黑名單，以及「這個詞在過半數的區都出現 ⇒ 擋掉」的相對判準。
#: 使用者兩次否決：「深度學習沒什麼不好呀」「我覺得不用特別擋名字」。他是對的——
#:
#: ① 我量錯了東西：**「這個詞在別區的成員文字裡出現過」≠「這個名字套在別區上也說得通」**。
#:    領域術語是整個庫的背景詞彙，到處都會出現，但只有一區**是在講它**。
#: ② 更根本的：名字好不好是**語意判斷**，而**介面本來就讓你改名**。
#:    後端替你否決，等於把你的裁決搶過來——而且它用的還是一個代理指標。
#:
#: ⇒ 程式只管**格式**（空的、過長、重名）。名字好不好交給那句
#:   「它跟哪幾區容易混、這個名字怎麼分開」——**由人判**。


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
            # ⚠️ 退路**標籤先說「未命名」**，後面才給錨當提示。
            #    截斷的句子（「Single Source of Tru」）**冒充**名字；
            #    `未命名（20 件）· 錨：…` 誠實說了它沒名字，只是幫你認出是哪一區。
            "name": f"未命名（{len(mem)} 件）· 錨：{label[anchor][:12]}",
            "_samples": [label[n] for n in _spread(near)],
            "parent": "", "anchor": {"kind": anchor[0], "ref": anchor[1]},
            # ⚠️ 理由要**可判斷**：列錨與代表成員，你能說「不對，這些跟那條沒關係」。
            #    分數（0.87）不是理由——它不可反駁。
            "reasons": [f"這 {len(mem)} 件都最靠近〈{label[anchor][:34]}〉",
                        "最靠近中心的幾件：" + "、".join(label[n][:18] for n in near[1:4])],
            "edges": [],
            "items": [{"kind": n[0], "ref": n[1], "label": label[n]} for n in mem],
            "count": len(mem), "suggest_apply": True,
        })
    _name_all(out, chat)                     # ⚠️ 一次全部命名——兄弟要互相區分
    for g in out:
        g.pop("_samples", None)
    return out


class _Dead:
    def reply(self, messages):
        raise RuntimeError("沒有 LLM")


def _spread(near: list, n: int = 12) -> list:
    """從**由近到遠排好**的成員裡均勻取樣。

    ⚠️ 不能只取最靠近中心的——那會讓名字描述**錨附近那幾件**，而不是這一區。
    取樣要涵蓋**廣度**，名字才擔得起整區。
    """
    if len(near) <= n:
        return list(near)
    step = (len(near) - 1) / (n - 1)
    return [near[round(i * step)] for i in range(n)]


def _name_all(groups: list[dict], chat) -> None:
    """一次幫**所有區**命名，就地寫回 `name`。

    ⚠️ 一區一次呼叫的話，LLM **看不到別的區**，也就不知道要排除掉什麼
    ——而「這個名字排除掉了哪些區」正是判斷它有沒有修剪力的方式。
    ⇒ 同一層的兄弟要**一起**命名。（但跨層不要一起：那會湊出一個可疑地整齊的分類學。）
    """
    if chat is None or not groups:
        return
    body = "\n\n".join(
        f"[{i}]\n" + "\n".join(f"- {t[:60]}" for t in g["_samples"])
        for i, g in enumerate(groups))
    try:
        raw = chat.reply([{"role": "system", "content": _NAME},
                          {"role": "user", "content": body}]) or ""
    except Exception:  # noqa: BLE001 - 命名失敗不該擋住劃界
        return
    got: dict = {}
    for line in raw.splitlines():
        if "｜" not in line and "|" not in line:
            continue
        parts = [x.strip() for x in line.replace("|", "｜").split("｜")]
        idx = "".join(ch for ch in parts[0] if ch.isdigit())
        nm = parts[1].strip("「」\"'") if len(parts) > 1 else ""
        why = parts[2] if len(parts) > 2 else ""
        if idx.isdigit() and 1 < len(nm) <= 20:      # 只驗格式，不評價名字
            got[int(idx)] = (nm, why)
    seen: set = set()
    for i, g in enumerate(groups):
        nm, why = got.get(i, ("", ""))
        # ⚠️ 模型說「未命名」時**用我們的退路**（帶件數與錨），不要用那個裸字：
        #    裸的「未命名」既認不出是哪一區，又會跟另一個「未命名」撞名。
        if nm in ("未命名", "無", "N/A", "none", "None"):
            nm = ""
        # ⚠️ 名字必須彼此不同——兩個同名的資料夾等於沒有分區
        if nm and nm not in seen:
            g["name"] = nm
            seen.add(nm)
            # ⚠️ 把「它跟哪幾區容易搞混、這個名字怎麼分開」放進理由：
            #    ① 逼模型真的做那個自我檢查（要寫出來才做得到）
            #    ② 你看得到，所以你能反駁——判準①要的正是這個
        # 理由**不管有沒有取到名字都留著**——取不出來的原因跟名字一樣值得看
        if why:
            g["reasons"].append((f"取這個名字：" if nm else "取不出名字：") + why[:70])
