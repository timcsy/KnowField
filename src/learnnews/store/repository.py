"""Repository：SQLite 之上的 CRUD（對應 data-model.md 實體）。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from ..models import (
    Article,
    BehaviorSignal,
    Digest,
    DigestEntry,
    Figure,
    InterestProfile,
    Item,
    Source,
)
from ..rag.types import CorpusEntry, Vector
from .schema import init_db


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class Repository:
    """對 SQLite 的存取層。傳入 db_path（":memory:" 供測試）。"""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)

    def close(self) -> None:
        self.conn.close()

    # --- Source ---
    def upsert_source(self, s: Source) -> None:
        self.conn.execute(
            "INSERT INTO sources (id, name, type, access_method, endpoint, enabled,"
            " last_fetch_at, last_status) VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET name=excluded.name, type=excluded.type,"
            " access_method=excluded.access_method, endpoint=excluded.endpoint,"
            " enabled=excluded.enabled, last_fetch_at=excluded.last_fetch_at,"
            " last_status=excluded.last_status",
            (s.id, s.name, s.type, s.access_method, s.endpoint, int(s.enabled),
             _iso(s.last_fetch_at), s.last_status),
        )
        self.conn.commit()

    def set_source_enabled(self, source_id: str, enabled: bool) -> None:
        self.conn.execute(
            "UPDATE sources SET enabled=? WHERE id=?", (int(enabled), source_id)
        )
        self.conn.commit()

    def delete_source(self, source_id: str) -> None:
        """刪除一個來源（spec 008）。digest 僅在來源全空時重種預設 → 刪除被尊重。"""
        self.conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
        self.conn.commit()

    def list_sources(self, enabled_only: bool = False) -> list[Source]:
        sql = "SELECT * FROM sources"
        if enabled_only:
            sql += " WHERE enabled=1"
        rows = self.conn.execute(sql + " ORDER BY id").fetchall()
        return [
            Source(
                id=r["id"], name=r["name"], type=r["type"],
                access_method=r["access_method"], endpoint=r["endpoint"],
                enabled=bool(r["enabled"]), last_fetch_at=_dt(r["last_fetch_at"]),
                last_status=r["last_status"] or "",
            )
            for r in rows
        ]

    # --- Item ---
    def add_item(self, item: Item) -> int:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO items (source_id, external_id, title, abstract, url,"
            " published_at, lang, cluster_id, fetched_at, content_hash)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (item.source_id, item.external_id, item.title, item.abstract, item.url,
             _iso(item.published_at), item.lang, item.cluster_id,
             _iso(item.fetched_at), item.content_hash),
        )
        self.conn.commit()
        if cur.lastrowid:
            item.id = cur.lastrowid
            return cur.lastrowid
        # content_hash 衝突：回傳既有列 id
        row = self.conn.execute(
            "SELECT id FROM items WHERE content_hash=?", (item.content_hash,)
        ).fetchone()
        item.id = row["id"] if row else None
        return item.id or 0

    # --- InterestProfile ---
    def get_interest_profile(self) -> InterestProfile:
        row = self.conn.execute(
            "SELECT * FROM interest_profile WHERE id=1"
        ).fetchone()
        return InterestProfile(
            explicit_topics=json.loads(row["explicit_topics"]),
            learned_weights=json.loads(row["learned_weights"]),
            updated_at=_dt(row["updated_at"]),
        )

    def save_interest_profile(self, p: InterestProfile) -> None:
        self.conn.execute(
            "UPDATE interest_profile SET explicit_topics=?, learned_weights=?,"
            " updated_at=? WHERE id=1",
            (json.dumps(p.explicit_topics, ensure_ascii=False),
             json.dumps(p.learned_weights, ensure_ascii=False),
             _iso(datetime(2026, 7, 23))),
        )
        self.conn.commit()

    # --- BehaviorSignal ---
    def add_behavior(self, sig: BehaviorSignal) -> None:
        self.conn.execute(
            "INSERT INTO behavior_signals (item_id, action, at) VALUES (?,?,?)",
            (sig.item_id, sig.action, _iso(sig.at)),
        )
        self.conn.commit()

    def list_behaviors(self) -> list[BehaviorSignal]:
        rows = self.conn.execute("SELECT * FROM behavior_signals").fetchall()
        return [
            BehaviorSignal(id=r["id"], item_id=r["item_id"], action=r["action"],
                           at=_dt(r["at"]))
            for r in rows
        ]

    # --- Digest ---
    def save_digest(self, d: Digest) -> int:
        cur = self.conn.execute(
            "INSERT INTO digests (date, truncated_count, missing_sources)"
            " VALUES (?,?,?)",
            (d.date, d.truncated_count,
             json.dumps(d.missing_sources, ensure_ascii=False)),
        )
        digest_id = cur.lastrowid or 0
        for e in d.entries:
            body = e.article.body if e.article else ""
            headline = e.article.headline if e.article else ""
            fig_url = e.article.figure.url if (e.article and e.article.figure) else ""
            fig_kind = e.article.figure.kind if (e.article and e.article.figure) else ""
            self.conn.execute(
                "INSERT INTO digest_entries (digest_id, rank, title, url, matched_topic,"
                " article_body, article_headline, figure_url, figure_kind, source_id)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (digest_id, e.rank, e.item.title, e.item.url, e.matched_topic,
                 body, headline, fig_url, fig_kind, e.item.source_id or ""),
            )
        self.conn.commit()
        d.id = digest_id
        return digest_id

    def recent_digest_titles(self, k: int = 3) -> list[str]:
        """最近 K 份『真實』匯整（排除種子容器）的條目標題——供趨勢讀數（spec 013）。"""
        from ..config import SEEDS_DATE
        rows = self.conn.execute(
            "SELECT id FROM digests WHERE date != ? ORDER BY id DESC LIMIT ?",
            (SEEDS_DATE, k)).fetchall()
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        q = ("SELECT title FROM digest_entries WHERE digest_id IN (%s) ORDER BY id"
             % ",".join("?" * len(ids)))
        return [r["title"] for r in self.conn.execute(q, ids).fetchall() if r["title"]]

    def get_last_digest(self) -> Digest | None:
        """讀最近一次落庫匯整的全部 entries，組回 Digest（供 web 首頁，data-model.md）。"""
        row = self.conn.execute(
            "SELECT id, date, truncated_count, missing_sources FROM digests"
            " ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        rows = self.conn.execute(
            "SELECT id, rank, title, url, matched_topic, article_body, article_headline,"
            " figure_url, figure_kind, source_id FROM digest_entries"
            " WHERE digest_id=? ORDER BY rank",
            (row["id"],),
        ).fetchall()
        entries: list[DigestEntry] = []
        for r in rows:
            figure = None
            if r["figure_url"]:
                figure = Figure(kind=r["figure_kind"], url=r["figure_url"],
                                source_note="")
            article = Article(item_id=0, body=r["article_body"], source_url=r["url"],
                              headline=r["article_headline"], figure=figure)
            item = Item(source_id=(r["source_id"] if "source_id" in r.keys() else "") or "",
                        external_id="", title=r["title"], url=r["url"])
            entries.append(DigestEntry(item=item, rank=r["rank"], relevance_score=0.0,
                                       article=article, matched_topic=r["matched_topic"],
                                       entry_id=r["id"]))   # spec 019：帶出條目 id
        return Digest(id=row["id"], date=row["date"], entries=entries,
                      truncated_count=row["truncated_count"],
                      missing_sources=json.loads(row["missing_sources"]))

    def get_last_digest_entry(self, rank: int) -> dict | None:
        """US2：取最近一次匯整的第 rank 則（title＋matched_topic）。"""
        row = self.conn.execute("SELECT MAX(id) AS mid FROM digests").fetchone()
        if not row or row["mid"] is None:
            return None
        entry = self.conn.execute(
            "SELECT title, url, matched_topic FROM digest_entries"
            " WHERE digest_id=? AND rank=?", (row["mid"], rank)
        ).fetchone()
        if entry is None:
            return None
        return {"title": entry["title"], "url": entry["url"],
                "matched_topic": entry["matched_topic"]}

    def get_entry_material(self, entry_id: int) -> tuple[str, str, str] | None:
        """spec 019：以 digest_entries.id 取任一條目材料（種子或每日流皆可）。
        回 (headline_or_title, body, url)；headline 優先（溯源）；不存在→None。純讀，不寫庫。"""
        r = self.conn.execute(
            "SELECT title, article_headline, article_body, url FROM digest_entries"
            " WHERE id=?", (entry_id,)).fetchone()
        if r is None:
            return None
        return (r["article_headline"] or r["title"], r["article_body"] or "", r["url"])

    # --- RAG 語料與嵌入（spec 005） ---
    def list_corpus_entries(self, today: bool = False) -> list[CorpusEntry]:
        """取語料條目。today=False＝全部匯整＋種子；True＝最近一份『真實』匯整（排除種子容器）。"""
        from ..config import SEEDS_DATE
        base = (
            "SELECT de.id AS eid, de.title, de.url, de.article_headline AS headline,"
            " de.article_body AS body, d.date AS ddate, de.source_class AS sclass"
            " FROM digest_entries de JOIN digests d ON de.digest_id=d.id"
        )
        if today:
            # 最近一份真實每日匯整（種子容器不算「今天」，spec 006 R2）
            row = self.conn.execute(
                "SELECT MAX(id) AS mid FROM digests WHERE date != ?", (SEEDS_DATE,)
            ).fetchone()
            if not row or row["mid"] is None:
                return []
            rows = self.conn.execute(
                base + " WHERE de.digest_id=? ORDER BY de.id", (row["mid"],)
            ).fetchall()
        else:
            rows = self.conn.execute(base + " ORDER BY de.id").fetchall()
        entries = [
            CorpusEntry(entry_id=r["eid"], title=r["title"], url=r["url"],
                        headline=r["headline"] or "", body=r["body"] or "",
                        digest_date=r["ddate"],
                        source_class=r["sclass"] or "ordinary")
            for r in rows
        ]
        if not today:
            # 已冊封 why-node 也是語料——最重的吸引子。負 entry_id 避與 digest_entries 碰撞（spec 012）。
            entries.extend(self._anointed_corpus_entries())
        return entries

    def _anointed_corpus_entries(self) -> list[CorpusEntry]:
        import json as _json
        out: list[CorpusEntry] = []
        for r in self.conn.execute(
                "SELECT id, claim, evidence_urls, ladder FROM why_nodes"
                " WHERE status='anointed'"
        ).fetchall():
            urls = _json.loads(r["evidence_urls"] or "[]")
            claim = r["claim"] or ""
            ladder = _json.loads((r["ladder"] if "ladder" in r.keys() else "[]") or "[]")
            # body 併入 why 階梯：深層 why 也進檢索，問到底層邏輯也撈得到（品質補強）
            body = claim + ("\n" + "\n".join(ladder) if ladder else "")
            out.append(CorpusEntry(
                entry_id=-r["id"], title=f"根因：{claim[:40]}",
                url=(urls[0] if urls else ""), headline="", body=body,
                digest_date="", source_class="root"))
        return out

    # --- 種子 ingest（spec 006） ---
    def get_or_create_seeds_digest(self) -> int:
        """種子容器：哨兵 date 的 digests 列（無則建），種子皆插為它的 entries。"""
        from ..config import SEEDS_DATE
        row = self.conn.execute(
            "SELECT id FROM digests WHERE date=?", (SEEDS_DATE,)).fetchone()
        if row:
            return row["id"]
        cur = self.conn.execute(
            "INSERT INTO digests (date, truncated_count, missing_sources)"
            " VALUES (?,0,'[]')", (SEEDS_DATE,))
        self.conn.commit()
        return cur.lastrowid or 0

    def seed_exists(self, url: str) -> str | None:
        """種子去重：容器內已有 canonical_url 相同者 → 回其標題（FR-004/007）。

        SeedService 在抓取前把 ref 正規化成 canonical 原文 URL（arXiv → abs 裸 id URL）再查，
        故同篇多寫法會歸一。
        """
        from ..config import SEEDS_DATE
        from ..sources.base import canonical_url
        target = canonical_url(url)
        for r in self.conn.execute(
            "SELECT de.title, de.url FROM digest_entries de JOIN digests d"
            " ON de.digest_id=d.id WHERE d.date=?", (SEEDS_DATE,)
        ).fetchall():
            if canonical_url(r["url"]) == target:
                return r["title"]
        return None

    def ingest_seed(self, item, article, source_class: str = "ordinary") -> int:
        """插入一筆種子 entry 到種子容器，回 entry_id（FR-001）。"""
        digest_id = self.get_or_create_seeds_digest()
        fig_url = article.figure.url if article.figure else ""
        fig_kind = article.figure.kind if article.figure else ""
        rank = self.conn.execute(
            "SELECT COALESCE(MAX(rank),0)+1 AS r FROM digest_entries WHERE digest_id=?",
            (digest_id,)).fetchone()["r"]
        cur = self.conn.execute(
            "INSERT INTO digest_entries (digest_id, rank, title, url, matched_topic,"
            " article_body, article_headline, figure_url, figure_kind, source_class)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (digest_id, rank, item.title, item.url, "", article.body,
             article.headline, fig_url, fig_kind, source_class))
        self.conn.commit()
        return cur.lastrowid or 0

    # --- 知識庫管理（spec 007，皆僅限種子容器 → 每日流結構性唯讀） ---
    def _seeds_digest_id(self) -> int | None:
        from ..config import SEEDS_DATE
        row = self.conn.execute(
            "SELECT id FROM digests WHERE date=?", (SEEDS_DATE,)).fetchone()
        return row["id"] if row else None

    def list_field_attractors(self) -> list[CorpusEntry]:
        """場的吸引子＝人冊封的種子＋已冊封根因（spec 018）。不含每日流（流是水、非吸引子）。"""
        return self.list_seeds() + self._anointed_corpus_entries()

    def list_seeds(self) -> list[CorpusEntry]:
        """列出種子容器裡的種子（新在上）；不含每日流（FR-001/005）。"""
        from ..config import SEEDS_DATE
        rows = self.conn.execute(
            "SELECT de.id AS eid, de.title, de.url, de.article_headline AS headline,"
            " de.article_body AS body, d.date AS ddate, de.source_class AS sclass"
            " FROM digest_entries de JOIN digests d ON de.digest_id=d.id"
            " WHERE d.date=? ORDER BY de.id DESC", (SEEDS_DATE,)).fetchall()
        return [
            CorpusEntry(entry_id=r["eid"], title=r["title"], url=r["url"],
                        headline=r["headline"] or "", body=r["body"] or "",
                        digest_date=r["ddate"], source_class=r["sclass"] or "ordinary")
            for r in rows
        ]

    def delete_seed(self, entry_id: int) -> bool:
        """刪一則種子（限種子容器）；連 entry_embeddings 一起清（無孤兒，FR-003）。
        非種子（每日流/不存在）→ 回 False 不動作（流唯讀，FR-005）。"""
        sid = self._seeds_digest_id()
        if sid is None:
            return False
        row = self.conn.execute(
            "SELECT id FROM digest_entries WHERE id=? AND digest_id=?",
            (entry_id, sid)).fetchone()
        if row is None:
            return False
        self.conn.execute("DELETE FROM digest_entries WHERE id=?", (entry_id,))
        self.conn.execute("DELETE FROM entry_embeddings WHERE entry_id=?", (entry_id,))
        self.conn.commit()
        return True

    # --- why-node 根因（spec 012） ---
    def add_why_node(self, claim: str, evidence_urls: list, touchstones: list,
                     fog_flag: bool, source_entry_id: int, created_at: str,
                     ladder: list | None = None) -> int:
        """新增候選 why-node（狀態=candidate），回 id。"""
        import json as _json
        cur = self.conn.execute(
            "INSERT INTO why_nodes (claim, evidence_urls, touchstones, ladder, fog_flag,"
            " status, source_entry_id, created_at) VALUES (?,?,?,?,?,'candidate',?,?)",
            (claim, _json.dumps(evidence_urls, ensure_ascii=False),
             _json.dumps(touchstones, ensure_ascii=False),
             _json.dumps(ladder or [], ensure_ascii=False), 1 if fog_flag else 0,
             source_entry_id, created_at))
        self.conn.commit()
        return cur.lastrowid

    def list_why_nodes(self, status: str | None = None) -> list:
        import json as _json

        from ..rootcause.extract import WhyNode
        sql = "SELECT * FROM why_nodes"
        args: tuple = ()
        if status:
            sql += " WHERE status=?"
            args = (status,)
        sql += " ORDER BY id DESC"
        out = []
        for r in self.conn.execute(sql, args).fetchall():
            out.append(WhyNode(
                id=r["id"], claim=r["claim"],
                evidence_urls=_json.loads(r["evidence_urls"] or "[]"),
                touchstones=_json.loads(r["touchstones"] or "[]"),
                ladder=_json.loads((r["ladder"] if "ladder" in r.keys() else "[]") or "[]"),
                fog_flag=bool(r["fog_flag"]), status=r["status"],
                source_entry_id=r["source_entry_id"] or 0,
                created_at=r["created_at"] or ""))
        return out

    def anoint_why_node(self, wid: int, claim: str | None = None) -> bool:
        """人冊封：狀態 → anointed（可同時改 claim）。回是否有更新。"""
        if claim is not None and claim.strip():
            cur = self.conn.execute(
                "UPDATE why_nodes SET status='anointed', claim=? WHERE id=?",
                (claim.strip(), wid))
        else:
            cur = self.conn.execute(
                "UPDATE why_nodes SET status='anointed' WHERE id=?", (wid,))
        self.conn.commit()
        return cur.rowcount > 0

    def delete_why_node(self, wid: int) -> bool:
        """刪 why-node，連其負 id 嵌入一起清（無孤兒）。"""
        cur = self.conn.execute("DELETE FROM why_nodes WHERE id=?", (wid,))
        self.conn.execute("DELETE FROM entry_embeddings WHERE entry_id=?", (-wid,))
        self.conn.commit()
        return cur.rowcount > 0

    # --- 對話的「由來」存檔（spec 023，episodes 層）---
    def save_conversation(self, title: str, messages: list,
                          why_node_id: int | None = None) -> int:
        """存下整段對話（人按才呼叫）。**指紋冪等**（spec 025）：同一段對話已存過→回既有 id、
        不新增複本；否則新增。why_node_id 給定時，把連結存在 why_nodes 側（多條根因可共用一份）。"""
        from datetime import datetime, timezone

        from ..chat.capture import conversation_fingerprint
        fp = conversation_fingerprint(messages)
        cid = None
        for r in self.conn.execute(
                "SELECT id, messages FROM conversations ORDER BY id ASC").fetchall():
            if conversation_fingerprint(json.loads(r["messages"] or "[]")) == fp:
                cid = r["id"]          # 同段已存→共用（不插入、不刪改既有）
                break
        if cid is None:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            cur = self.conn.execute(
                "INSERT INTO conversations (title, messages, why_node_id, created_at)"
                " VALUES (?,?,?,?)",
                (title, json.dumps(messages, ensure_ascii=False), why_node_id, now))
            cid = cur.lastrowid
        if why_node_id is not None:    # 連結存 why_node 側（事實來源）
            self.conn.execute(
                "UPDATE why_nodes SET conversation_id=? WHERE id=?", (cid, why_node_id))
        self.conn.commit()
        return cid

    def _row_to_conversation(self, r):
        from ..models import Conversation
        return Conversation(
            id=r["id"], title=r["title"] or "",
            messages=json.loads(r["messages"] or "[]"),
            why_node_id=r["why_node_id"], created_at=r["created_at"] or "")

    def list_conversations(self) -> list:
        rows = self.conn.execute(
            "SELECT id, title, messages, why_node_id, created_at FROM conversations"
            " ORDER BY id DESC").fetchall()
        return [self._row_to_conversation(r) for r in rows]

    def get_conversation(self, cid: int):
        r = self.conn.execute(
            "SELECT id, title, messages, why_node_id, created_at FROM conversations"
            " WHERE id=?", (cid,)).fetchone()
        return self._row_to_conversation(r) if r else None

    def dedupe_plan(self):
        """算既有重複對話清理計畫（spec 026）。唯讀、不寫庫。"""
        from ..chat.capture import plan_dedupe
        convos = [{"id": c.id, "messages": c.messages} for c in self.list_conversations()]
        return plan_dedupe(convos, self.why_node_provenance())

    def apply_dedupe(self) -> dict:
        """執行清理（人確認後）：重指根因由來連結＋刪多餘份。只動連結與多餘對話，不碰根因主張。"""
        plan = self.dedupe_plan()
        for wid, survivor in plan.repoint.items():
            self.conn.execute(
                "UPDATE why_nodes SET conversation_id=? WHERE id=?", (survivor, wid))
        for cid in plan.delete_ids:
            self.conn.execute("DELETE FROM conversations WHERE id=?", (cid,))
        self.conn.commit()
        return {"groups": plan.n_groups, "removed": plan.n_extra,
                "repointed": plan.n_roots}

    def why_node_provenance(self) -> dict:
        """{why_node_id: conversation_id}——供 /roots 顯示「← 由來」（spec 025 改讀 why_node 側，
        多條根因可映同一 cid）。只含連結非空、且該對話仍存在者（JOIN conversations）。刪根因→列消→自動不含。"""
        out: dict = {}
        for r in self.conn.execute(
            "SELECT w.id AS wid, w.conversation_id AS cid FROM why_nodes w"
            " JOIN conversations c ON c.id=w.conversation_id"
            " WHERE w.conversation_id IS NOT NULL").fetchall():
            out[r["wid"]] = r["cid"]
        return out

    def set_seed_class(self, entry_id: int, cls: str) -> bool:
        """重分類種子（限種子容器）。cls∈{explainer,ordinary}；否則/非種子 → 回 False。"""
        if cls not in ("explainer", "ordinary"):
            return False
        sid = self._seeds_digest_id()
        if sid is None:
            return False
        cur = self.conn.execute(
            "UPDATE digest_entries SET source_class=? WHERE id=? AND digest_id=?",
            (cls, entry_id, sid))
        self.conn.commit()
        return cur.rowcount > 0

    def get_entry_embedding(self, entry_id: int, tag: str) -> Vector | None:
        row = self.conn.execute(
            "SELECT vector_json FROM entry_embeddings WHERE entry_id=? AND tag=?",
            (entry_id, tag),
        ).fetchone()
        return json.loads(row["vector_json"]) if row else None

    def save_entry_embedding(self, entry_id: int, tag: str, vec: Vector) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO entry_embeddings (entry_id, tag, dim, vector_json)"
            " VALUES (?,?,?,?)",
            (entry_id, tag, len(vec), json.dumps(vec)),
        )
        self.conn.commit()

    def ensure_embeddings(self, entries: list[CorpusEntry], embedder,
                          tag: str) -> dict[int, Vector]:
        """回傳 {entry_id: 向量}；缺 tag 者以 embed_many **批次**補算並落庫（FR-009/010）。

        不在迴圈裡逐一 embed（experience 教訓：逐一呼叫慢又觸發額度隔離）。
        """
        vecs: dict[int, Vector] = {}
        missing: list[CorpusEntry] = []
        for e in entries:
            v = self.get_entry_embedding(e.entry_id, tag)
            if v is None:
                missing.append(e)
            else:
                vecs[e.entry_id] = v
        if missing:
            computed = embedder.embed_many([e.embed_text() for e in missing])
            for e, v in zip(missing, computed):
                self.save_entry_embedding(e.entry_id, tag, v)
                vecs[e.entry_id] = v
        return vecs
