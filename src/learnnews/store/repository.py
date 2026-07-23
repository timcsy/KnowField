"""Repository：SQLite 之上的 CRUD（對應 data-model.md 實體）。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from ..models import (
    BehaviorSignal,
    Digest,
    InterestProfile,
    Item,
    Source,
)
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
        self.conn.commit()
        d.id = cur.lastrowid
        return cur.lastrowid or 0
