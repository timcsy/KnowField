"""spec 065：建議怎麼整理。

核心分工：**成員來自結構，命名與合併才交給 LLM。**

⚠️ 為什麼不用 embedding 相似度分群——它給不出**可查證的理由**。
「這 7 條來自〈某段互動〉」你可以點開去看；「它們都跟生成模型有關」你**沒辦法不同意**。
而不可反駁的理由等於沒有理由，於是介面會被橡皮圖章化（spec 046 的教訓）。
⇒ 所以分群只走**既有的邊**：由來 · 帶入物 · 佐證來源。
"""
from __future__ import annotations

_PROMPT = (
    "下面是一些**已經分好的群**，每群有一個 id 和一句「它們為什麼在一起」的事實。\n"
    "把這些群**歸併**成 3–7 個資料夾，給每個資料夾一個名字。\n"
    "規則：\n"
    "- 只能重組**群**，不能拆散群、也不能自己發明成員。\n"
    "- 名字要像資料夾名（短、名詞、看得懂），不要寫成句子。\n"
    "- 分不出來的群**可以不放進任何資料夾**——留白比硬分好。\n"
    "- 可以有一層父子：父夾寫在第三欄，沒有就寫 -。\n"
    "每行一個資料夾，格式：\n"
    "夾：<名字>｜<群 id，逗號分隔>｜<父夾名字或 ->\n"
    "只輸出這些行，不要別的字。"
)


def _live_unfiled(repo) -> dict:
    """未歸屬（在根領域）且活著的東西，依種類分。"""
    out: dict = {"why_node": {}, "conversation": {}, "source": {}, "article": {}}
    for row in repo._inventory_rows():
        if row.get("domain_id") is None and row["kind"] in out:
            out[row["kind"]][row["ref"]] = row.get("label") or str(row["ref"])
    return out


def structural_groups(repo) -> list[dict]:
    """把未歸屬的知識按**既有的邊**分群。

    每群帶 `edge`＝那條邊本身（kind, ref）⇒ 理由**指得出具體的東西**，可以被反駁。
    落單的（沒有任何邊）收成一群並標 `lonely`——**允許留白**，不硬分（FR-005）。
    """
    unfiled = _live_unfiled(repo)
    groups: list[dict] = []
    used: set[tuple] = set()

    # ① 由來：同一段互動冊封出來的理解 ＋ 那段互動自己
    #    ⚠️ 互動要一起搬——否則理解進了資料夾，它的由來留在外面。
    by_conv: dict = {}
    for wid in unfiled["why_node"]:
        w = repo.conn.execute(
            f"SELECT conversation_id FROM why_nodes WHERE {repo._OWN} AND id=%s", (wid,)).fetchone()
        cid = w["conversation_id"] if w else None
        if cid:
            by_conv.setdefault(int(cid), []).append(wid)
    for cid, wids in by_conv.items():
        title = unfiled["conversation"].get(cid) or repo.conn.execute(
            f"SELECT title FROM conversations WHERE {repo._OWN} AND id=%s", (cid,)).fetchone()
        title = title if isinstance(title, str) else ((title["title"] if title else "") or f"互動 #{cid}")
        items = [{"kind": "why_node", "ref": w, "label": unfiled["why_node"][w]} for w in wids]
        if cid in unfiled["conversation"]:
            items.append({"kind": "conversation", "ref": cid, "label": title})
        groups.append({
            "id": f"g{len(groups) + 1}",
            # ⚠️ 理由是要被讀的，量詞錯了會讓人覺得這句是機器湊的 ⇒ 不可信 ⇒ 不會細看
            "reason": (f"這條理解是從〈{title}〉這段互動冊封出來的" if len(wids) == 1
                       else f"這 {len(wids)} 條理解都是從〈{title}〉這段互動冊封出來的"),
            "edge": ("conversation", cid),
            "items": items,
        })
        used |= {(i["kind"], i["ref"]) for i in items}

    # ② 帶入物：帶著同一份來源開的互動 ＋ 那份來源
    by_src: dict = {}
    for cid in unfiled["conversation"]:
        if (("conversation", cid)) in used:
            continue
        r = repo.conn.execute(
            f"SELECT carried_kind, carried_ref FROM conversations WHERE {repo._OWN} AND id=%s",
            (cid,)).fetchone()
        if r and r["carried_kind"] == "source" and r["carried_ref"]:
            by_src.setdefault(r["carried_ref"], []).append(cid)
    for url, cids in by_src.items():
        label = unfiled["source"].get(url) or url
        items = [{"kind": "conversation", "ref": c, "label": unfiled["conversation"][c]} for c in cids]
        if url in unfiled["source"]:
            items.append({"kind": "source", "ref": url, "label": label})
        groups.append({
            "id": f"g{len(groups) + 1}",
            "reason": (f"這段互動是帶著〈{label}〉這份來源開的" if len(cids) == 1
                       else f"這 {len(cids)} 段互動都是帶著〈{label}〉這份來源開的"),
            "edge": ("source", url),
            "items": items,
        })
        used |= {(i["kind"], i["ref"]) for i in items}

    # ③ 落單的：**不建議分**（留白）
    lonely = [{"kind": k, "ref": ref, "label": lbl}
              for k, d in unfiled.items() for ref, lbl in d.items() if (k, ref) not in used]
    if lonely:
        groups.append({
            "id": f"g{len(groups) + 1}",
            # ⚠️ 這裡不能寫 markdown：介面是純文字渲染，星號會原樣漏到畫面上
            "reason": f"這 {len(lonely)} 件目前沒有任何連結，不建議現在分"
                      f"——等它們被引用或被聊到再說",
            "edge": ("none", None),
            "items": lonely,
            "lonely": True,
        })
    return groups


def _parse_folders(raw: str) -> list[dict]:
    out = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line.startswith("夾："):
            continue
        parts = [p.strip() for p in line[2:].split("｜")]
        if len(parts) < 2 or not parts[0]:
            continue
        ids = [x.strip() for x in parts[1].split(",") if x.strip()]
        parent = parts[2] if len(parts) > 2 and parts[2] not in ("-", "") else ""
        out.append({"name": parts[0], "group_ids": ids, "parent": parent})
    return out


def suggest_folders(repo, chat) -> list[dict]:
    """結構群 → LLM 命名／合併 → 建議的資料夾。

    ⚠️ FR-003：LLM 掛掉就**退回結構群本身**，不是回空的
    ——回空的會讓使用者以為「沒東西可整理」，那是把故障畫成結論。
    """
    groups = structural_groups(repo)
    real = [g for g in groups if not g.get("lonely")]
    by_id = {g["id"]: g for g in real}

    named: list[dict] = []
    if real:
        lines = "\n".join(f"{g['id']}：{g['reason']}（{len(g['items'])} 件）" for g in real)
        try:
            parsed = _parse_folders(chat.reply(
                [{"role": "system", "content": _PROMPT}, {"role": "user", "content": lines}]))
        except Exception:  # noqa: BLE001 - 建議失敗不該炸，退回結構
            parsed = []
        for f in parsed:
            gs = [by_id[i] for i in f["group_ids"] if i in by_id]
            if not gs:                    # ⚠️ LLM 指了不存在的群 ⇒ 丟掉，不是憑空生一個空夾
                continue
            named.append(_folder(f["name"], gs, f["parent"]))
        covered = {gid for f in parsed for gid in f["group_ids"] if gid in by_id}
        leftovers = [g for g in real if g["id"] not in covered]
    else:
        leftovers = []
    # LLM 沒處理到的（或整個失敗）→ 一群一夾，名字用它自己的邊
    named += [_folder(_auto_name(g), [g], "") for g in leftovers]

    for g in groups:
        if g.get("lonely"):
            f = _folder("還沒有連結的", [g], "")
            f["lonely"] = True
            f["suggest_apply"] = False     # 留白：不建議套用
            named.append(f)
    return named


def _auto_name(g: dict) -> str:
    kind, ref = g["edge"]
    label = g["items"][0]["label"] if g["items"] else "未命名"
    return (label[:20] if kind == "source" else _edge_title(g))


def _edge_title(g: dict) -> str:
    r = g["reason"]
    a, b = r.find("〈"), r.find("〉")
    return r[a + 1:b][:20] if 0 <= a < b else "未命名"


def _folder(name: str, groups: list[dict], parent: str) -> dict:
    items = [i for g in groups for i in g["items"]]
    return {
        "name": name or "未命名",
        "parent": parent,
        # ⚠️ 合併之後**每一群的理由都要留著**——理由是逐條可查證的，不能被摘要掉
        "reasons": [g["reason"] for g in groups],
        "edges": [list(g["edge"]) for g in groups],
        "items": items,
        "count": len(items),
        "suggest_apply": True,
    }
