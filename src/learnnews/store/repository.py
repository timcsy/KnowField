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
                " article_body, article_headline, figure_url, figure_kind)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (digest_id, e.rank, e.item.title, e.item.url, e.matched_topic,
                 body, headline, fig_url, fig_kind),
            )
        self.conn.commit()
        d.id = digest_id
        return digest_id

    def get_last_digest(self) -> Digest | None:
        """讀最近一次落庫匯整的全部 entries，組回 Digest（供 web 首頁，data-model.md）。"""
        row = self.conn.execute(
            "SELECT id, date, truncated_count, missing_sources FROM digests"
            " ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        rows = self.conn.execute(
            "SELECT rank, title, url, matched_topic, article_body, article_headline,"
            " figure_url, figure_kind FROM digest_entries WHERE digest_id=? ORDER BY rank",
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
            item = Item(source_id="", external_id="", title=r["title"], url=r["url"])
            entries.append(DigestEntry(item=item, rank=r["rank"], relevance_score=0.0,
                                       article=article, matched_topic=r["matched_topic"]))
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

    # --- RAG 語料與嵌入（spec 005） ---
    def list_corpus_entries(self, today: bool = False) -> list[CorpusEntry]:
        """取語料條目。today=False＝全部匯整；True＝最近一份匯整（data-model.md R6）。"""
        base = (
            "SELECT de.id AS eid, de.title, de.url, de.article_headline AS headline,"
            " de.article_body AS body, d.date AS ddate"
            " FROM digest_entries de JOIN digests d ON de.digest_id=d.id"
        )
        if today:
            row = self.conn.execute("SELECT MAX(id) AS mid FROM digests").fetchone()
            if not row or row["mid"] is None:
                return []
            rows = self.conn.execute(
                base + " WHERE de.digest_id=? ORDER BY de.id", (row["mid"],)
            ).fetchall()
        else:
            rows = self.conn.execute(base + " ORDER BY de.id").fetchall()
        return [
            CorpusEntry(entry_id=r["eid"], title=r["title"], url=r["url"],
                        headline=r["headline"] or "", body=r["body"] or "",
                        digest_date=r["ddate"])
            for r in rows
        ]

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
