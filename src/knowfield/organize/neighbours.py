"""spec 070：領域頁的鄰居與岔路。

判準（spec 066 立的）：**如果這個介面給你的東西，搜尋也給得了，它就不該存在。**

搜尋是零副作用的——你問什麼得到什麼。而搜尋給不了的，是**你沒在找的東西**。
⇒ 這支模組算的三樣，就是那個副作用：**通往哪裡** · **快掉出去的** · **相鄰的區**。
以前它們是 scope 的副產品；現在它們就是產品。
"""
from __future__ import annotations

import math
from collections import defaultdict


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def _norm(v):
    s = math.sqrt(sum(a * a for a in v)) or 1.0
    return [a / s for a in v]


def _cen(vs):
    n = len(vs[0])
    c = [0.0] * n
    for v in vs:
        for i, a in enumerate(v):
            c[i] += a
    return _norm([a / len(vs) for a in c])


def _crossings(repo, did: int | None) -> list[dict]:
    """這一區的東西連到哪些**別的區**，各幾條。只靠**真實的邊**（由來／引用／帶入）
    ⇒ 沒有向量時它照樣算得出來。"""
    names = {d["id"]: d["name"] for d in repo.list_domains()}
    mine = [(r["kind"], r["ref"]) for r in repo._inventory_rows() if r.get("domain_id") == did]
    seen: set = set()
    cnt: dict = defaultdict(int)
    for kind, ref in mine:
        for nb in repo._neighbours(kind, ref):
            nk, nr = (nb["kind"], nb["ref"]) if isinstance(nb, dict) else nb
            other = repo.knowledge_domain(nk, nr)
            if other == did:
                continue                      # 同區的不是岔路
            key = tuple(sorted([str((kind, ref)), str((nk, nr))]))
            if key in seen:
                continue
            seen.add(key)
            cnt[other] += 1
    return sorted(
        ({"domain_id": k, "name": names.get(k) or ("根領域" if k is None else f"#{k}"),
          "count": v} for k, v in cnt.items()),
        key=lambda x: -x["count"])


def _vectors(repo, embedder) -> dict:
    """已經落庫的向量（**不呼叫 API**）——逛一頁不該花錢，也不該等。"""
    import json as _json
    if embedder is None:
        return {}
    tag = getattr(embedder, "tag", None) or "openai-text-embedding-3-small"
    vec = {}
    for x in repo.conn.execute("SELECT entry_id, vector_json FROM entry_embeddings"
                               " WHERE tag=%s", (tag,)).fetchall():
        vec[int(x["entry_id"])] = _json.loads(x["vector_json"])
    return vec


def _pos_of(repo, vec, rows) -> dict:
    """(kind, ref) → 向量。只用已落庫的；取不到就沒有位置（不補算）。"""
    out = {}
    chunks = defaultdict(list)
    if any(r["kind"] == "source" for r in rows):
        for x in repo.conn.execute("SELECT id, url FROM digest_entries").fetchall():
            if int(x["id"]) in vec:
                chunks[x["url"]].append(vec[int(x["id"])])
    cw = defaultdict(list)
    for x in repo.conn.execute("SELECT id, conversation_id FROM why_nodes"
                               " WHERE conversation_id IS NOT NULL").fetchall():
        if -int(x["id"]) in vec:
            cw[int(x["conversation_id"])].append(vec[-int(x["id"])])
    for r in rows:
        k = (r["kind"], r["ref"])
        if k[0] == "why_node" and -int(k[1]) in vec:
            out[k] = _norm(vec[-int(k[1])])
        elif k[0] == "source" and k[1] in chunks:
            out[k] = _cen(chunks[k[1]])
        elif k[0] == "conversation" and int(k[1]) in cw:
            out[k] = _cen(cw[int(k[1])])
    return out


def domain_context(repo, did: int | None, embedder) -> dict:
    """搜尋給不了的那三塊。

    ⚠️ `has_geometry=False` 時 🪂🧭 是**空的**，而介面必須說「算不出來」而不是顯示空的
    ——**三塊一起沉默地失效，比少一塊更糟**：你會以為這一區真的沒有鄰居。
    """
    rows = repo._inventory_rows()
    vec = _vectors(repo, embedder)
    pos = _pos_of(repo, vec, rows) if vec else {}
    mine = [r for r in rows if r.get("domain_id") == did]
    mine_pos = {(r["kind"], r["ref"]): pos[(r["kind"], r["ref"])]
                for r in mine if (r["kind"], r["ref"]) in pos}

    out = {"crossings": _crossings(repo, did), "fringe": [], "nearby": [],
           "has_geometry": bool(mine_pos)}
    if not mine_pos:
        return out

    c = _cen(list(mine_pos.values()))
    label = {(r["kind"], r["ref"]): (r.get("label") or str(r["ref"])) for r in mine}
    # 🪂 由遠而近：⚠️ 它們可能該搬，**也可能是橋**——只讓你看見，不替你決定
    far = sorted(((1 - _cos(v, c), k) for k, v in mine_pos.items()), reverse=True)[:4]
    out["fringe"] = [{"kind": k[0], "ref": k[1], "label": label[k],
                      "dist": round(d, 2)} for d, k in far if d > 0.15]

    # 🧭 相鄰的區：各區重心之間的距離
    names = {d["id"]: d["name"] for d in repo.list_domains()}
    cents = {}
    for dom in set(r.get("domain_id") for r in rows):
        if dom == did:
            continue
        vs = [pos[(r["kind"], r["ref"])] for r in rows
              if r.get("domain_id") == dom and (r["kind"], r["ref"]) in pos]
        if vs:
            cents[dom] = _cen(vs)
    out["nearby"] = [
        {"domain_id": k, "name": names.get(k) or ("根領域" if k is None else f"#{k}"),
         "dist": round(1 - _cos(c, v), 2)}
        for k, v in sorted(cents.items(), key=lambda kv: -_cos(c, kv[1]))[:3]]
    return out
