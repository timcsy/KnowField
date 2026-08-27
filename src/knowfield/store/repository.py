"""Repository：資料層 CRUD（對應 data-model.md 實體）。

spec 034＋036：資料層走可攜 adapter（`store/db.py`）——本地 SQLite（零 server）或 prod Postgres，由連線字串決定。
SQL 一律寫 `%s`＋RETURNING＋ON CONFLICT（adapter 對 SQLite 翻 `?`）。r["c"]／r.keys()／dict(r) 兩後端相容；
自增 id 用 RETURNING（取代 lastrowid）。
"""

from __future__ import annotations

import json
import os
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


#: spec 063（階段 58）：帶 `owner_id` 的表——**每一個**碰到它們的查詢都要帶 owner 條件。
#: ⚠️ join 表（`entry_embeddings`／`article_roots`）刻意不在內：它們**只經父 id 存取**，
#: 而父 id 一定來自一個已經過濾過的查詢 ⇒ 加 owner 只是重複，不加也不會外洩。
OWNED_TABLES = ("domains", "why_nodes", "articles", "conversations", "digest_entries",
                "ext_bases", "ext_items", "ext_paths", "ext_lessons",
                "ext_chunks")

#: 既有的單一使用者。⚠️ 補欄的 `DEFAULT 1` 讓「加欄」本身就是 backfill。
DEFAULT_OWNER = 1


class Repository:
    """可攜資料層存取（spec 036）。傳入連線字串：PG DSN（postgresql://…）或 SQLite（檔案路徑/:memory:/sqlite://…）；
    None→讀 env KNOWFIELD_DATABASE_URL，仍空→預設本地 SQLite 檔（零 server 本地預設）。

    `owner`（spec 063）＝這個 repo 看得到誰的資料。**過濾在這一層，不在呼叫端**——
    ⚠️ 漏一個條件會顯示別人的知識而且不報錯，所以它不能靠記性：
    `tests/unit/test_tenant_isolation.py` 會掃原始碼，任何碰到 `OWNED_TABLES`
    卻沒帶 `_OWN` 的查詢都讓測試變紅（刻意的例外要寫 `# owner-exempt: 理由`）。
    """

    def __init__(self, dsn: str | None = None, owner: int = DEFAULT_OWNER,
                 persona: int | None = None) -> None:
        from . import db
        dsn = dsn or os.environ.get("KNOWFIELD_DATABASE_URL") or "knowfield.db"
        self.conn = db.connect(dsn)
        # ⚠️ 強制轉 int：述詞是直接嵌進 SQL 的（跟 `_LIVE` 同一種常數），
        #    owner／persona 不是使用者輸入，但這兩行讓它們**不可能**是。
        self.owner = int(owner)
        self.persona = int(persona) if persona else None
        self._OWN = self._own()
        # 寫入時填的身分：`NULL` ＝ 共用。⚠️ 預設歸**當前身分**（同「出生就歸位」：
        # 不問你，從脈絡決定）——問使用者「這要放哪個身分」等於每次寫入都收一次稅。
        self._P = "NULL" if self.persona is None else str(self.persona)
        init_db(self.conn)

    def close(self) -> None:
        self.conn.close()

    def _insert_id(self, sql: str, params: tuple) -> int:
        """執行 INSERT … RETURNING id，回新 id（取代 SQLite lastrowid）。"""
        row = self.conn.execute(sql + " RETURNING id", params).fetchone()
        return int(row["id"]) if row else 0

    # --- Source ---
    def upsert_source(self, s: Source) -> None:
        self.conn.execute(
            "INSERT INTO sources (id, name, type, access_method, endpoint, enabled,"
            " last_fetch_at, last_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
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
            "UPDATE sources SET enabled=%s WHERE id=%s", (int(enabled), source_id)
        )
        self.conn.commit()

    def delete_feed(self, source_id: str) -> None:
        """刪除一個**訂閱來源**（`sources` 表，spec 008）——RSS 那種，不是你收進的資料。

        ⚠️ 它本來叫 `delete_source`，而**下面有另一支同名的**（封存收進的來源，spec 055）
        ——後定義的會蓋掉前面的 ⇒ **這一支從那天起就到不了**。
        兩個呼叫點都傳 url，所以沒有人踩到；但那是運氣，不是設計。
        ⇒ 判準：**同一個類別裡出現同名方法，那不是重載，是其中一支已經死了。**
        """
        self.conn.execute("DELETE FROM sources WHERE id=%s", (source_id,))
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
        row = self.conn.execute(
            "INSERT INTO items (source_id, external_id, title, abstract, url,"
            " published_at, lang, cluster_id, fetched_at, content_hash)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT (content_hash) DO NOTHING RETURNING id",
            (item.source_id, item.external_id, item.title, item.abstract, item.url,
             _iso(item.published_at), item.lang, item.cluster_id,
             _iso(item.fetched_at), item.content_hash),
        ).fetchone()
        self.conn.commit()
        if row:
            item.id = int(row["id"])
            return item.id
        # content_hash 衝突：回傳既有列 id
        existing = self.conn.execute(
            "SELECT id FROM items WHERE content_hash=%s", (item.content_hash,)
        ).fetchone()
        item.id = existing["id"] if existing else None
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
            "UPDATE interest_profile SET explicit_topics=%s, learned_weights=%s,"
            " updated_at=%s WHERE id=1",
            (json.dumps(p.explicit_topics, ensure_ascii=False),
             json.dumps(p.learned_weights, ensure_ascii=False),
             _iso(datetime(2026, 7, 23))),
        )
        self.conn.commit()

    # --- BehaviorSignal ---
    def add_behavior(self, sig: BehaviorSignal) -> None:
        self.conn.execute(
            "INSERT INTO behavior_signals (item_id, action, at) VALUES (%s,%s,%s)",
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
        digest_id = self._insert_id(
            "INSERT INTO digests (date, truncated_count, missing_sources)"
            " VALUES (%s,%s,%s)",
            (d.date, d.truncated_count,
             json.dumps(d.missing_sources, ensure_ascii=False)),
        )
        for e in d.entries:
            body = e.article.body if e.article else ""
            headline = e.article.headline if e.article else ""
            fig_url = e.article.figure.url if (e.article and e.article.figure) else ""
            fig_kind = e.article.figure.kind if (e.article and e.article.figure) else ""
            self.conn.execute(
                "INSERT INTO digest_entries (digest_id, rank, title, url, matched_topic,"
                f" article_body, article_headline, figure_url, figure_kind, source_id, owner_id, persona_id)"
                f" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,{self.owner},{self._P})",
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
            "SELECT id FROM digests WHERE date != %s ORDER BY id DESC LIMIT %s",
            (SEEDS_DATE, k)).fetchall()
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        placeholders = ",".join(["%s"] * len(ids))
        q = (f"SELECT title FROM digest_entries WHERE {self._OWN} AND digest_id IN ({placeholders})"
             " ORDER BY id")
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
            f" WHERE {self._OWN} AND digest_id=%s ORDER BY rank",
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
            f" WHERE {self._OWN} AND digest_id=%s AND rank=%s", (row["mid"], rank)
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
            f" WHERE {self._OWN} AND id=%s", (entry_id,)).fetchone()
        if r is None:
            return None
        return (r["article_headline"] or r["title"], r["article_body"] or "", r["url"])

    # --- RAG 語料與嵌入（spec 005） ---
    def list_corpus_entries(self, today: bool = False, domain=None) -> list[CorpusEntry]:
        """取語料條目。today=False＝全部匯整＋種子；True＝最近一份『真實』匯整（排除種子容器）。

        spec 079：`domain` ⇒ **只取那個領域及其子孫底下的**。
        ⚠️ `None` ＝ 照舊（整個場），既有呼叫點行為一個字都不變。
        ⚠️ 而縮範圍時**不含未歸屬的**——「站在這裡」的意思是「這裡有的東西」，
           而未歸屬的**不在任何地方**。（把它們算進來，站哪裡都一樣，那就等於沒縮。）
        """
        from ..config import SEEDS_DATE
        scope = ""
        if domain is not None:
            ids = self.domain_descendants(int(domain)) | {int(domain)}
            scope = f" AND de.domain_id IN ({','.join(str(int(i)) for i in ids)})"
        base = (
            "SELECT de.id AS eid, de.title, de.url, de.article_headline AS headline,"
            " de.article_body AS body, d.date AS ddate, de.source_class AS sclass"
            f" FROM digest_entries de JOIN digests d ON de.digest_id=d.id"
            # ⚠️ spec 064：**遺骸不進語料**。這一行原本不在，於是封存過的來源
            #    仍在影響每一個回答——而清單頁是對的，所以完全看不出來。
            f" WHERE {self._own('de')} AND {self._live('de')}{scope}"
        )
        if today:
            # 最近一份真實每日匯整（種子容器不算「今天」，spec 006 R2）
            row = self.conn.execute(
                "SELECT MAX(id) AS mid FROM digests WHERE date != %s", (SEEDS_DATE,)
            ).fetchone()
            if not row or row["mid"] is None:
                return []
            rows = self.conn.execute(
                base + " AND de.digest_id=%s ORDER BY de.id", (row["mid"],)
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
            # ⚠️ 它們也有 `domain_id` ⇒ **同樣吃領域**。漏掉的話，縮了範圍卻仍拿整個場的
            #    理解當地基——而那是**最重的**吸引子，等於根本沒縮。
            entries.extend(self._anointed_corpus_entries(domain))
        return entries

    def anointed_ids_in_domain(self, domain) -> set:
        """某個領域（含子孫）底下、已冊封的理解 id。

        ⚠️ 存在的理由：`WhyNode` **沒有 `domain_id` 欄位**，所以在物件上
        `getattr(r, "domain_id", None)` 永遠是 `None` ⇒ 拿它過濾會**濾掉全部**，
        而且不會報錯——只會讓聊天忽然沒有任何理解可用。
        """
        ids = self.domain_descendants(int(domain)) | {int(domain)}
        return {int(r["id"]) for r in self.conn.execute(
            f"SELECT id FROM why_nodes WHERE {self._OWN} AND status='anointed'"
            f" AND {self._LIVE} AND domain_id IN ({','.join(str(int(i)) for i in ids)})"
        ).fetchall()}

    def _anointed_corpus_entries(self, domain=None) -> list[CorpusEntry]:
        import json as _json
        scope = ""
        if domain is not None:
            ids = self.domain_descendants(int(domain)) | {int(domain)}
            scope = f" AND domain_id IN ({','.join(str(int(i)) for i in ids)})"
        out: list[CorpusEntry] = []
        for r in self.conn.execute(
                f"SELECT id, claim, evidence_urls, ladder FROM why_nodes"
                f" WHERE {self._OWN} AND status='anointed' AND {self._LIVE}{scope}"  # spec 055：遺骸不餵給聊天／RAG
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

    # ── 複習（spec 068）：一天三條 ────────────────────────────────────
    def rehearse(self, n: int = 3) -> list[dict]:
        """挑幾條以前冊封的理解推到眼前。**同一天內回同樣那幾條**。

        ⚠️ 挑選依據**只有時間**（最久沒出現過的優先，沒出現過的最優先）。
        絕不用採用次數／被引用數——那是馬太陷阱：被引用最多的會一直被推出來，
        而**你最需要重新遇到的正好是你快忘了的那些**。
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        today = now[:10]
        rows = self.conn.execute(
            f"SELECT id, claim, kind FROM why_nodes WHERE {self._OWN} AND {self._LIVE}"
            f" AND status='anointed' AND COALESCE(last_rehearsed_at,'') LIKE %s"
            f" ORDER BY id LIMIT {int(n)}", (f"{today}%",)).fetchall()
        if not rows:                     # 今天還沒推過 ⇒ 挑最久沒出現的，並蓋上今天
            rows = self.conn.execute(
                f"SELECT id, claim, kind FROM why_nodes WHERE {self._OWN} AND {self._LIVE}"
                f" AND status='anointed'"
                f" ORDER BY COALESCE(last_rehearsed_at,'') ASC, id ASC LIMIT {int(n)}").fetchall()
            for r in rows:
                self.conn.execute(
                    f"UPDATE why_nodes SET last_rehearsed_at=%s WHERE {self._OWN} AND id=%s",
                    (now, r["id"]))
            self.conn.commit()
        return [{"id": r["id"], "claim": r["claim"] or "",
                 "kind": (r["kind"] if "kind" in r.keys() else "") or ""} for r in rows]

    # ── persona（spec 067）：隱私的**硬**隔離 ─────────────────────────
    #
    # 過濾不在這裡——它在 `_own()`，跟 owner **共用同一個述詞**。
    # ⚠️ 那是刻意的：88 個查詢點因此自動涵蓋 persona，
    #    **隱私上線不需要再改一次那 88 個地方**（而「再改一次」正是會漏的那一次）。
    def create_persona(self, name: str, color: str = "") -> int:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        wid = self._insert_id(
            f"INSERT INTO personas (owner_id, name, color, created_at)"
            f" VALUES ({self.owner},%s,%s,%s)", (name.strip()[:40], color, now))
        self.conn.commit()
        return wid

    def list_personas(self) -> list[dict]:
        # owner-exempt: personas 表沒有 persona_id（身分不隸屬於身分），只依 owner 分
        return [dict(r) for r in self.conn.execute(
            f"SELECT id, name, color FROM personas WHERE owner_id={self.owner} ORDER BY id")]

    def rename_persona(self, pid: int, name: str) -> None:
        # owner-exempt: 同上
        self.conn.execute(
            f"UPDATE personas SET name=%s WHERE owner_id={self.owner} AND id=%s",
            (name.strip()[:40], int(pid)))
        self.conn.commit()

    # ── 全域搜尋（spec 066）──────────────────────────────────────────
    #
    # ⚠️ 搜尋是**最容易漏掉硬邊界**的地方——它天生的動作就是「把全部撈出來」。
    # 所以這裡的每一句都必須帶 `_OWN` ＋ `_LIVE`，一句都不能少：
    # 漏掉 owner ＝ 顯示別人的知識；漏掉 live ＝ 遺骸回到活的場（spec 064 才修過同一族）。
    _SEARCH = [
        # (kind, 表, 識別欄, 標題欄, 要比對的欄位…)
        ("why_node", "why_nodes", "id", "claim", ("claim", "ladder")),
        ("conversation", "conversations", "id", "title", ("title", "messages")),
        ("article", "articles", "id", "title", ("topic", "title", "markdown")),
        ("source", "digest_entries", "url", "title", ("title", "article_body", "note")),
    ]

    #: spec 074：**外部知識也搜得到**——「Spark 跟即時通訊搜不到彼此」就是那個病。
    #: ⚠️ 但它**不進 `list_corpus_entries`**：搜尋是「找得到」，語料是聊天時的**地基**。
    #:    混為一談的話，別人的判準會**沒有經過冊封**就開始影響你的回答（原則 6 那道膜）。
    _SEARCH_EXT = ("ext", "ext_items", "id", "path", ("path", "body"))

    def search(self, q: str, per_kind: int = 8) -> list[dict]:
        """跨四種知識的字面搜尋。回 [{kind, ref, label}]，**不排序跨種**（分組交給呼叫端）。

        ⚠️ 比對**標題與內容**，不只標題——只比標題等於只找得到你已經記得名字的東西。
        """
        term = (q or "").strip().lower()
        if not term:                      # 空字串不查庫（也不該回「全部」）
            return []
        like = f"%{term}%"
        out: list[dict] = []
        for kind, table, idcol, titlecol, cols in self._SEARCH:
            where = " OR ".join(f"LOWER(COALESCE({c},'')) LIKE %s" for c in cols)
            rows = self.conn.execute(
                f"SELECT DISTINCT {idcol} AS ref, MIN({titlecol}) AS label FROM {table}"
                f" WHERE {self._OWN} AND {self._LIVE} AND ({where})"
                f" GROUP BY {idcol} LIMIT {int(per_kind)}",
                tuple([like] * len(cols))).fetchall()
            for r in rows:
                out.append({"kind": kind, "ref": r["ref"],
                            "label": (r["label"] or str(r["ref"]))[:120]})
        # 外部知識：⚠️ 它沒有 archived/erased（重抓就整批取代）⇒ 不套 `_LIVE`；
        #           而每一筆**一定要帶 base**——看不出是誰的，就等於冒充你自己的知識。
        _, table, idcol, titlecol, cols = self._SEARCH_EXT
        where = " OR ".join(f"LOWER(COALESCE(i.{c},'')) LIKE %s" for c in cols)
        for r in self.conn.execute(
                f"SELECT i.{idcol} AS ref, i.{titlecol} AS label, i.layer, b.repo, b.id AS base_id"
                f" FROM ext_items i JOIN ext_bases b ON b.id=i.base_id"
                f" WHERE {self._own('i')} AND ({where})"
                f" ORDER BY i.id LIMIT {int(per_kind)}",
                tuple([like] * len(cols))).fetchall():
            out.append({"kind": "ext", "ref": r["ref"],
                        "label": (r["label"] or "")[:120],
                        "base": r["repo"].rsplit("/", 1)[-1], "layer": r["layer"] or "",
                        "base_id": r["base_id"]})
        return out

    def ext_item(self, iid: int) -> dict:
        r = self.conn.execute(
            "SELECT i.*, b.repo FROM ext_items i JOIN ext_bases b ON b.id=i.base_id"
            f" WHERE {self._own('i')} AND i.id=%s", (iid,)).fetchone()
        return dict(r) if r else {}

    #: spec 076：進得了「站在專案裡聊」那個語料的層。
    #: ⚠️ 只有這四層——`history`／`episodes` 是**場景**不是判準，`draft` 是未定的，
    #:    `skills` 是步驟。而**哪幾層進了語料要說出來**，否則「答不出來」會被讀成「它不知道」。
    CHAT_LAYERS = ("experience", "concepts", "principles", "vision")
    _CHUNK = 1200          # 字。⚠️ 最大一份 226,460 字，整份塞不進 context

    @classmethod
    def chunk_markdown(cls, text: str, size: int = 0) -> list[str]:
        """依標題切，過大的再硬切。

        ⚠️ 先照 `##`／`###` 切，是因為 knowie 的檔案**本來就是一段一個主張**
        ——照字數盲切會把一條判準腰斬，而腰斬過的塊檢索得到也讀不懂。
        """
        size = size or cls._CHUNK
        blocks, cur = [], []
        for line in (text or "").splitlines():
            if line.startswith(("## ", "### ")) and cur:
                blocks.append("\n".join(cur)); cur = []
            cur.append(line)
        if cur:
            blocks.append("\n".join(cur))
        out = []
        for b in blocks:
            b = b.strip()
            if not b:
                continue
            while len(b) > size:
                cut = b.rfind("\n", 0, size)
                cut = cut if cut > size // 2 else size
                out.append(b[:cut].strip()); b = b[cut:].strip()
            if b:
                out.append(b)
        return out

    def project_sources(self, prefix: str) -> list[dict]:
        """spec 080 FR-004：這個專案底下**活著的來源**（一檔一列，路徑從 url 還原）。

        ⚠️ 讀的是**來源**，不是 `ext_items` 快照。快照是「抓下來的那一刻的樣子」，
           而回答用的是來源——樹顯示快照就是在給你看**場沒有在用的東西**，
           而且兩邊不一致時**沒有任何人會發現**（封存過的檔還留在樹上）。
        """
        from ..config import SEEDS_DATE
        rows = self.conn.execute(
            "SELECT de.url AS url, COUNT(*) AS chunks FROM digest_entries de"
            f" JOIN digests d ON de.digest_id=d.id WHERE {self._own('de')}"
            f" AND {self._live('de')} AND d.date=%s AND de.url LIKE %s"
            " GROUP BY de.url ORDER BY de.url", (SEEDS_DATE, prefix + "%")).fetchall()
        n = len(prefix)
        return [{"path": r["url"][n:], "url": r["url"], "chunks": int(r["chunks"])}
                for r in rows]

    def stale_project_sources(self, prefix: str, alive: set) -> list:
        """這個專案底下、**已經不在 repo 裡**的來源 url。

        ⚠️ 不處理的話它們會永遠留著、而且**還在語料裡**——你以為場反映那個專案
        現在的樣子，其實混著幾個月前刪掉的東西，而且不會報錯。
        """
        rows = self.conn.execute(
            f"SELECT DISTINCT url FROM digest_entries WHERE {self._OWN} AND {self._LIVE}"
            " AND url LIKE %s", (prefix + "%",)).fetchall()
        return [r["url"] for r in rows if r["url"] not in alive]

    def delete_ext_base(self, bid: int) -> bool:
        """移除一個外部知識庫——**四張表一起清**。

        ⚠️ 這裡是**真的刪**，不是封存：外部知識是**別人 repo 的快照**，
        重加一次就回來了 ⇒ 沒有「遺骸」要留（spec 055 那套是給**你自己的**知識用的，
        因為那些刪掉就真的沒了）。
        ⚠️ 而**已經收進場的借來判準不動**——它們是 `why_nodes`，你冊封過，那是你的了。
        """
        r = self.conn.execute(
            f"SELECT id FROM ext_bases WHERE {self._OWN} AND id=%s", (bid,)).fetchone()
        if not r:
            return False
        for t in ("ext_items", "ext_paths", "ext_lessons", "ext_chunks"):
            self.conn.execute(f"DELETE FROM {t} WHERE {self._OWN} AND base_id=%s", (bid,))
        self.conn.execute(f"DELETE FROM ext_bases WHERE {self._OWN} AND id=%s", (bid,))
        self.conn.commit()
        return True

    # --- 種子 ingest（spec 006） ---
    def get_or_create_seeds_digest(self) -> int:
        """種子容器：哨兵 date 的 digests 列（無則建），種子皆插為它的 entries。"""
        from ..config import SEEDS_DATE
        row = self.conn.execute(
            "SELECT id FROM digests WHERE date=%s", (SEEDS_DATE,)).fetchone()
        if row:
            return row["id"]
        did = self._insert_id(
            "INSERT INTO digests (date, truncated_count, missing_sources)"
            " VALUES (%s,0,'[]')", (SEEDS_DATE,))
        self.conn.commit()
        return did

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
            f" ON de.digest_id=d.id WHERE {self._own('de')} AND d.date=%s", (SEEDS_DATE,)
        ).fetchall():
            if canonical_url(r["url"]) == target:
                return r["title"]
        return None

    def ingest_seed(self, item, article, source_class: str = "ordinary",
                    note: str = "", ingested_at: str = "") -> int:
        """插入一筆種子 entry 到種子容器，回 entry_id（FR-001）。note＝收進原因、ingested_at＝收進日期。"""
        digest_id = self.get_or_create_seeds_digest()
        fig_url = article.figure.url if article.figure else ""
        fig_kind = article.figure.kind if article.figure else ""
        rank = self.conn.execute(
            f"SELECT COALESCE(MAX(rank),0)+1 AS r FROM digest_entries WHERE {self._OWN} AND digest_id=%s",
            (digest_id,)).fetchone()["r"]
        eid = self._insert_id(
            "INSERT INTO digest_entries (digest_id, rank, title, url, matched_topic,"
            " article_body, article_headline, figure_url, figure_kind, source_class,"
            f" note, ingested_at, owner_id, persona_id)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,{self.owner},{self._P})",
            (digest_id, rank, item.title, item.url, "", article.body,
             article.headline, fig_url, fig_kind, source_class, note, ingested_at))
        self.conn.commit()
        return eid

    # --- 知識庫管理（spec 007，皆僅限種子容器 → 每日流結構性唯讀） ---
    def _seeds_digest_id(self) -> int | None:
        from ..config import SEEDS_DATE
        row = self.conn.execute(
            "SELECT id FROM digests WHERE date=%s", (SEEDS_DATE,)).fetchone()
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
            f" WHERE {self._own('de')} AND d.date=%s AND {self._live('de')}"    # spec 055/064：遺骸不進語料
            " ORDER BY de.id DESC", (SEEDS_DATE,)).fetchall()
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
            f"SELECT id FROM digest_entries WHERE {self._OWN} AND id=%s AND digest_id=%s",
            (entry_id, sid)).fetchone()
        if row is None:
            return False
        self.conn.execute(f"DELETE FROM digest_entries WHERE {self._OWN} AND id=%s", (entry_id,))
        self.conn.execute("DELETE FROM entry_embeddings WHERE entry_id=%s", (entry_id,))
        self.conn.commit()
        return True

    # --- 收進來源（spec 031：同 url 的塊＝一份來源；管理/檢視用來源、檢索用塊，無新表） ---
    #: 專案落成的來源長這樣（`_base_to_sources`）——**這個 scheme 只有它會產生**。
    PROJECT_URL_PREFIX = "github://"

    def project_domain_ids(self) -> set:
        """哪些領域是**專案的**（`ext_bases.domain_id` 及其子孫）。

        ⚠️ 這是思考／開發之間**唯一那條線**。使用者：「不要把開發模式的來源
        歸換在互動模式的裡面」——而它不只是來源：對話、理解、應用、子領域
        全都要照同一條線切，否則你會在某一格看到專案的東西、在別格看不到，
        而**不一致比全有或全無更難察覺**。
        ⚠️ 一份判準、一個地方——兩套會漂，而漂掉的那一套不會報錯。
        """
        roots = [int(r["domain_id"]) for r in self.conn.execute(
            f"SELECT domain_id FROM ext_bases WHERE {self._OWN}"
            " AND domain_id IS NOT NULL").fetchall()]
        # ⚠️ 沒有專案就**一個查詢結束**：這條線每一次領域視野都會走，
        #    而每個 base 各跑一次 `domain_descendants` 讓整套測試慢了 50%。
        if not roots:
            return set()
        kids: dict = {}
        for d in self.list_domains():
            kids.setdefault(d["parent_id"], []).append(d["id"])
        out, stack = set(), list(roots)
        while stack:
            did = stack.pop()
            if did in out:
                continue
            out.add(did)
            stack.extend(kids.get(did, []))
        return out

    def list_source_groups(self, projects: bool = True) -> list[dict]:
        """種子容器裡的塊按 url 歸成「來源」，一來源一列（新在上）。

        ⚠️ `projects=False` ＝ 濾掉**專案落成的來源**。使用者：「為何開發的來源
        都跑到互動模式那邊了？」——226 份專案檔會把他自己收的 9 筆壓到看不見。
        ⚠️ 而它們**仍在語料裡、仍會被引用** ⇒ 少了它們的那一頁**要說出來**，
        否則就變成「看不到卻會影響回答」，那正是這個庫記過的那種沉默。
        """
        from ..config import SEEDS_DATE
        hide = set() if projects else self.project_domain_ids()
        skip = ("" if not hide else
                f" AND (de.domain_id IS NULL OR de.domain_id NOT IN"
                f" ({','.join(str(int(i)) for i in hide)}))")
        rows = self.conn.execute(
            "SELECT de.url AS url, MIN(de.title) AS title, COUNT(*) AS n,"
            " MIN(de.source_class) AS sclass, MIN(de.id) AS first_id, MAX(de.id) AS last_id,"
            " MIN(de.note) AS note, MIN(de.ingested_at) AS ingested_at"
            " FROM digest_entries de JOIN digests d ON de.digest_id=d.id"
            f" WHERE {self._own('de')} AND d.date=%s AND COALESCE(de.archived_at,'')=''"
            f"{skip} GROUP BY de.url ORDER BY MAX(de.id) DESC", (SEEDS_DATE,)).fetchall()
        return [{"url": r["url"], "title": r["title"] or r["url"], "count": r["n"],
                 "source_class": r["sclass"] or "ordinary", "first_id": r["first_id"],
                 "note": r["note"] or "", "ingested_at": r["ingested_at"] or ""}
                for r in rows]

    def set_source_meta(self, url: str, note: str, ingested_at: str) -> int:
        """編輯一來源的收進原因＋日期（套用到該來源所有塊；限種子容器）。回更新塊數。"""
        sid = self._seeds_digest_id()
        if sid is None:
            return 0
        cur = self.conn.execute(
            f"UPDATE digest_entries SET note=%s, ingested_at=%s WHERE {self._OWN} AND digest_id=%s AND url=%s",
            (note, ingested_at, sid, url))
        self.conn.commit()
        return cur.rowcount

    def source_meta(self, url: str) -> dict:
        """一來源的 note＋ingested_at（供詳情頁顯示/編輯）。"""
        from ..config import SEEDS_DATE
        r = self.conn.execute(
            "SELECT de.note, de.ingested_at FROM digest_entries de"
            f" JOIN digests d ON de.digest_id=d.id WHERE {self._own('de')} AND d.date=%s AND de.url=%s LIMIT 1",
            (SEEDS_DATE, url)).fetchone()
        return {"note": (r["note"] if r else "") or "", "ingested_at": (r["ingested_at"] if r else "") or ""}

    def get_source_chunks(self, url: str) -> list[str]:
        """一來源（url）的塊文，依序（供詳情頁拼回）。"""
        from ..config import SEEDS_DATE
        rows = self.conn.execute(
            "SELECT de.article_body AS body FROM digest_entries de"
            f" JOIN digests d ON de.digest_id=d.id WHERE {self._own('de')} AND d.date=%s AND de.url=%s ORDER BY de.id ASC",
            (SEEDS_DATE, url)).fetchall()
        return [r["body"] or "" for r in rows]

    def source_title(self, url: str) -> str:
        from ..config import SEEDS_DATE
        r = self.conn.execute(
            "SELECT de.title FROM digest_entries de JOIN digests d ON de.digest_id=d.id"
            f" WHERE {self._own('de')} AND d.date=%s AND de.url=%s LIMIT 1", (SEEDS_DATE, url)).fetchone()
        return (r["title"] if r else "") or url

    def delete_source(self, url: str, now: str = "") -> int:
        """**封存**一來源的所有塊（spec 055）——不再硬刪。回封存的塊數。

        ⚠️ **不清 embedding**（同 `delete_why_node`）：檢索已在語料層濾掉封存的，
        清它只會弄壞復原。向量在**抹除**時才清。
        """
        from datetime import datetime, timezone
        now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sid = self._seeds_digest_id()
        if sid is None:
            return 0
        ids = [r["id"] for r in self.conn.execute(
            f"SELECT id FROM digest_entries WHERE {self._OWN} AND digest_id=%s AND url=%s", (sid, url)).fetchall()]
        for eid in ids:
            self.conn.execute(
                f"UPDATE digest_entries SET archived_at=%s WHERE {self._OWN} AND id=%s", (now, eid))
        self.conn.commit()
        return len(ids)

    def set_source_class_by_url(self, url: str, source_class: str) -> int:
        """把一來源所有塊標成 source_class（整篇標解說文/改一般）。回更新塊數。"""
        sid = self._seeds_digest_id()
        if sid is None:
            return 0
        cur = self.conn.execute(
            f"UPDATE digest_entries SET source_class=%s WHERE {self._OWN} AND digest_id=%s AND url=%s",
            (source_class, sid, url))
        self.conn.commit()
        return cur.rowcount

    # --- why-node 根因（spec 012） ---
    def add_why_node(self, claim: str, evidence_urls: list, touchstones: list,
                     fog_flag: bool, source_entry_id: int, created_at: str,
                     ladder: list | None = None, kind: str = "",
                     src_from: int = 0, src_to: int = 0, source_quote: str = "",
                     source_page: int = 0, conversation_id: int | None = None,
                     origin: str = "") -> int:
        """新增候選 why-node（狀態=candidate），回 id。kind＝層次；src_from/to＝出處則數（階段29）；
        source_quote＝來源 verbatim 錨點（Text Fragment 由來定位）；source_page＝PDF 出處頁碼。"""
        import json as _json
        wid = self._insert_id(
            "INSERT INTO why_nodes (claim, evidence_urls, touchstones, ladder, fog_flag,"
            " kind, src_from, src_to, source_quote, source_page, status, source_entry_id,"
            f" conversation_id, origin, created_at, owner_id, persona_id)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'candidate',%s,%s,%s,%s,{self.owner},{self._P})",
            (claim, _json.dumps(evidence_urls, ensure_ascii=False),
             _json.dumps(touchstones, ensure_ascii=False),
             _json.dumps(ladder or [], ensure_ascii=False), 1 if fog_flag else 0,
             kind, src_from, src_to, source_quote, source_page, source_entry_id,
             conversation_id, origin, created_at))
        self.conn.commit()
        return wid

    def list_why_nodes(self, status: str | None = None) -> list:
        import json as _json

        from ..rootcause.extract import WhyNode
        sql = f"SELECT * FROM why_nodes WHERE {self._OWN} AND {self._LIVE}"    # spec 055：遺骸不進活清單
        args: tuple = ()
        if status:
            sql += " AND status=%s"
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
                created_at=r["created_at"] or "",
                kind=(r["kind"] if "kind" in r.keys() else "") or "",
                src_from=(r["src_from"] if "src_from" in r.keys() else 0) or 0,
                src_to=(r["src_to"] if "src_to" in r.keys() else 0) or 0,
                source_quote=(r["source_quote"] if "source_quote" in r.keys() else "") or "",
                source_page=(r["source_page"] if "source_page" in r.keys() else 0) or 0,
                origin=(r["origin"] if "origin" in r.keys() else "") or ""))
        return out

    def anoint_why_node(self, wid: int, claim: str | None = None,
                        kind: str | None = None) -> bool:
        """人冊封：狀態 → anointed（可同時改 claim／設認識論層次 kind）。回是否有更新。"""
        sets = ["status='anointed'"]
        args: list = []
        if claim is not None and claim.strip():
            sets.append("claim=%s"); args.append(claim.strip())
        if kind is not None:
            sets.append("kind=%s"); args.append(kind)
        args.append(wid)
        cur = self.conn.execute(
            f"UPDATE why_nodes SET {', '.join(sets)} WHERE {self._OWN} AND id=%s", tuple(args))
        self.conn.commit()
        return cur.rowcount > 0

    # ══ spec 072：別人的 base——場自己去 GitHub 拿回來的 ══
    def add_ext_base(self, repo: str, name: str = "", now: str = "") -> int:
        """登記一個要抓的 repo（狀態 pending）。同一個 repo 重複加＝回既有那筆。"""
        from datetime import datetime, timezone
        now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = self.conn.execute(
            f"SELECT id FROM ext_bases WHERE {self._OWN} AND repo=%s", (repo,)).fetchone()
        if r:
            return int(r["id"])
        bid = self._insert_id(
            "INSERT INTO ext_bases (repo, name, status, created_at, owner_id, persona_id)"
            f" VALUES (%s,%s,'pending',%s,{self.owner},{self._P})",
            (repo, name or repo.rsplit("/", 1)[-1], now))
        self.conn.commit()      # ⚠️ 少了這行：列在，但別的連線看不到 ⇒ 背景任務找不到它
        return bid

    def list_ext_bases(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT b.*,"
            " (SELECT COUNT(*) FROM ext_items i WHERE i.base_id=b.id) AS n_items"
            f" FROM ext_bases b WHERE {self._own('b')} ORDER BY b.id").fetchall()
        return [dict(r) for r in rows]

    def set_ext_domain(self, bid: int, did: int) -> None:
        """這個專案的來源歸在哪個領域。⚠️ **存下來**，不要之後靠 repo 名去撈——
        改個名就對不上，而對不上時聊天只是**少了證言**，不會有任何錯誤訊息。"""
        self.conn.execute(
            f"UPDATE ext_bases SET domain_id=%s WHERE {self._OWN} AND id=%s", (int(did), bid))
        self.conn.commit()

    def set_ext_status(self, bid: int, status: str, error: str = "") -> None:
        self.conn.execute(
            f"UPDATE ext_bases SET status=%s, error=%s WHERE {self._OWN} AND id=%s",
            (status, error[:500], bid))
        self.conn.commit()

    def save_ext_fetch(self, bid: int, fetched: dict, now: str = "") -> None:
        """一次抓取的結果落庫。**整批取代**——重抓就是重新對齊，不是累積。"""
        from datetime import datetime, timezone
        now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for t in ("ext_items", "ext_paths"):
            self.conn.execute(f"DELETE FROM {t} WHERE {self._OWN} AND base_id=%s", (bid,))
        for it in fetched["items"]:
            self.conn.execute(
                "INSERT INTO ext_items (base_id, layer, path, body, owner_id, persona_id)"
                f" VALUES (%s,%s,%s,%s,{self.owner},{self._P})",
                (bid, it["layer"], it["path"], it["body"]))
        for path in fetched["paths"]:
            self.conn.execute(
                "INSERT INTO ext_paths (base_id, path, owner_id, persona_id)"
                f" VALUES (%s,%s,{self.owner},{self._P})", (bid, path))
        self.conn.execute(
            "UPDATE ext_bases SET branch=%s, private=%s, fetched_at=%s, tree_truncated=%s,"
            f" n_paths=%s, status='ok', error='' WHERE {self._OWN} AND id=%s",
            (fetched["branch"], 1 if fetched["private"] else 0, now,
             1 if fetched["truncated"] else 0, len(fetched["paths"]), bid))
        self.conn.commit()

    def ext_layer_counts(self, bid: int) -> dict:
        rows = self.conn.execute(
            f"SELECT layer, COUNT(*) AS n FROM ext_items WHERE {self._OWN} AND base_id=%s"
            " GROUP BY layer", (bid,)).fetchall()
        return {r["layer"]: int(r["n"]) for r in rows}

    #: 只有這些副檔名算「路徑主張」。⚠️ 這是**機械可判**的界線——
    #: 不設的話會把 `3/64`（分數）、`why_nodes.kind`（欄位）、`id/topic/title`（欄位列表）
    #: 全報成死指標。實跑 KnowField 一度得到 296 條，其中真的只有個位數。
    _CODE_EXT = ("py", "ts", "tsx", "js", "mjs", "jsx", "json", "yaml", "yml", "toml",
                 "sh", "sql", "html", "css", "md", "txt", "cfg", "ini", "lock")
    #: 知識庫內部的相對引用（`history/040`、`concepts`）——沒有副檔名，靠前綴解。
    _KN_DIRS = ("history", "concepts", "episodes", "draft", "skills")

    def dead_refs(self, bid: int) -> dict:
        """知識檔案裡指到的路徑，而**那個路徑不在樹裡**。

        ⚠️ 只報**機器可判**的：有已知副檔名、或知識庫內部的相對引用。
        「這條來源寫得好不好」「該不該有來源」是語意判斷 ⇒ 不擋、不評分、不報。
        ⚠️ 而樹有抓取時間 ⇒ 回傳一定帶 `fetched_at`／`truncated`，
        否則這份報告會變成一份看起來很權威的過期漏報。
        """
        import re
        KN = "knowledge/"
        b = self.conn.execute(
            f"SELECT * FROM ext_bases WHERE {self._OWN} AND id=%s", (bid,)).fetchone()
        if not b:
            return {}
        paths = {r["path"] for r in self.conn.execute(
            f"SELECT path FROM ext_paths WHERE {self._OWN} AND base_id=%s", (bid,)).fetchall()}
        dirs = set()
        for x in paths:
            parts = x.split("/")
            for i in range(1, len(parts)):
                dirs.add("/".join(parts[:i]))
        # 知識檔案裡的引用多半**相對於 `knowledge/`**（`history/040`、`experience.md`）
        rel = {x[len(KN):] for x in paths | dirs if x.startswith(KN)}
        # ⚠️ 人會寫**部分路徑**（`store/schema.py` 指的是 `src/knowfield/store/schema.py`）
        #    ⇒ 用**後綴**比對，不是逐字相等。不這樣的話真的存在的檔案會被報成死的。
        by_name: dict[str, list[str]] = {}
        for x in paths:
            by_name.setdefault(x.rsplit("/", 1)[-1], []).append(x)

        def alive(ref: str) -> bool:
            if ref in paths or ref in dirs or ref in rel:
                return True
            if any(x.startswith((ref + "-", ref + ".", KN + ref + "-", KN + ref + "."))
                   for x in paths):                       # `history/040` ＝ 前綴
                return True
            return any(x == ref or x.endswith("/" + ref)
                       for x in by_name.get(ref.rsplit("/", 1)[-1], []))

        ext = "|".join(self._CODE_EXT)
        pat = re.compile(rf"`([A-Za-z0-9_./-]+\.(?:{ext})|(?:{'|'.join(self._KN_DIRS)})/[A-Za-z0-9_.-]+)`")
        out = []
        for r in self.conn.execute(
                f"SELECT path, body FROM ext_items WHERE {self._OWN} AND base_id=%s",
                (bid,)).fetchall():
            seen = set()
            for m in pat.finditer(r["body"] or ""):
                ref = m.group(1).rstrip("/")
                if ref in seen or "://" in ref:
                    continue
                seen.add(ref)
                if not alive(ref):
                    out.append({"file": r["path"], "ref": ref})
        return {"repo": b["repo"], "fetched_at": b["fetched_at"] or "",
                "truncated": bool(b["tree_truncated"]), "n_paths": len(paths),
                "dead": sorted(out, key=lambda x: (x["file"], x["ref"]))}

    # ══ spec 073：場自己算跨 base 群 ══
    def ext_items_of(self, bid: int) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT path, layer, body FROM ext_items"
            f" WHERE {self._OWN} AND base_id=%s", (bid,)).fetchall()]

    def sync_ext_lessons(self, bid: int, lessons: list[str]) -> None:
        """把抽出來的判準句對齊到 `ext_lessons`。

        ⚠️ **保留既有的向量**：只刪不見的、只加新的。整批重建的話，
        每次重算都要重新 embedding 一次——而那是真金白銀，還會慢到沒人願意按。
        """
        have = {r["text"]: r["id"] for r in self.conn.execute(
            f"SELECT id, text FROM ext_lessons WHERE {self._OWN} AND base_id=%s",
            (bid,)).fetchall()}
        want = set(lessons)
        for text, lid in have.items():
            if text not in want:
                self.conn.execute(f"DELETE FROM ext_lessons WHERE {self._OWN} AND id=%s", (lid,))
        for text in want - set(have):
            self.conn.execute(
                "INSERT INTO ext_lessons (base_id, text, owner_id, persona_id)"
                f" VALUES (%s,%s,{self.owner},{self._P})", (bid, text))
        self.conn.commit()

    def ext_lessons_missing_vectors(self, tag: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            f"SELECT id, text FROM ext_lessons WHERE {self._OWN}"
            " AND (tag<>%s OR COALESCE(vector_json,'')='')", (tag,)).fetchall()]

    def save_ext_vectors(self, rows: list[tuple[int, list]], tag: str) -> None:
        import json as _json
        for lid, vec in rows:
            self.conn.execute(
                f"UPDATE ext_lessons SET tag=%s, vector_json=%s WHERE {self._OWN} AND id=%s",
                (tag, _json.dumps(vec), lid))
        self.conn.commit()

    def ext_lesson_vectors(self, tag: str) -> tuple[dict, dict]:
        """回 `({base_name: [判準句…]}, {判準句: 向量})`。"""
        import json as _json
        bases: dict = {}
        vec: dict = {}
        for r in self.conn.execute(
                "SELECT b.repo, l.text, l.vector_json FROM ext_lessons l"
                " JOIN ext_bases b ON b.id=l.base_id"
                f" WHERE {self._own('l')} AND l.tag=%s AND COALESCE(l.vector_json,'')<>''",
                (tag,)).fetchall():
            name = r["repo"].rsplit("/", 1)[-1]
            bases.setdefault(name, []).append(r["text"])
            vec[r["text"]] = _json.loads(r["vector_json"])
        return bases, vec

    # ══ spec 071：跨 base 判準的收件匣 ══
    # ⚠️ **沒有新表。** 借來的判準就是一條 `status='candidate'` 的理解——
    #    既有的 `anoint_why_node` 就是那道人閘門，既有的理解頁就是複審的地方。
    #    形狀早就寫過（draft/room與組織的AI:132）：「共享空間必須是**收件匣，不是資料庫**」。
    BORROWED = "from:"          # origin 前綴＝這條是借來的

    def import_borrowed(self, groups: list, now: str = "") -> dict:
        """把跨 base 的群落成候選。回 `{"added": [id...], "skipped": n}`。

        一群 ＝ `{"claim": 代表句, "members": [{"base": .., "text": 原文}, ...]}`。
        ⚠️ **成員原文存進 `ladder`**——那不是挪用：ladder 本來就是「我憑什麼相信它」，
        而借來的判準憑的正是「**幾個獨立的 base 各自撞出同一條**」。
        ⚠️ **不合成**：claim 直接用代表句，人在冊封時可以改寫（`anoint_why_node` 本來就吃 claim）。
        """
        import json as _json
        from datetime import datetime, timezone

        from ..chat.capture import norm_claim
        now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # ⚠️ 去重要看**所有**理解，不只活的——略過（＝封存）過的不能再冒出來（FR-005）。
        #    這裡刻意不帶 `_LIVE`。
        # ⚠️ 而身分**不能只看 claim**：人在冊封時會把它改寫成自己的話（設計鼓勵這件事），
        #    改寫完就跟原本那群對不上，下次匯入整群復活。實跑才撞到——單元測試冊封時
        #    沒改寫，所以綠得毫無意義。⇒ 身分看**成員原文**（ladder），冊封不會動它。
        seen_claim, seen_rung = set(), set()
        for r in self.conn.execute(
                f"SELECT claim, ladder FROM why_nodes WHERE {self._OWN}").fetchall():
            if r["claim"]:
                seen_claim.add(norm_claim(r["claim"]))
            try:
                seen_rung.update(_json.loads(r["ladder"] or "[]"))
            except ValueError:
                pass
        added, skipped = [], 0
        for g in groups or []:
            claim = str((g or {}).get("claim") or "").strip()
            members = [m for m in ((g or {}).get("members") or [])
                       if str((m or {}).get("base") or "").strip()
                       and str((m or {}).get("text") or "").strip()]
            rungs = [f"{str(m['base']).strip()}｜{str(m['text']).strip()}" for m in members]
            key = norm_claim(claim)
            if (not claim or not members or key in seen_claim
                    or any(r in seen_rung for r in rungs)):
                skipped += 1
                continue
            seen_claim.add(key)                  # 同一批裡重複的也只收一次
            seen_rung.update(rungs)
            bases = sorted({str(m["base"]).strip() for m in members})
            added.append(self.add_why_node(
                claim=claim, evidence_urls=[], touchstones=[], fog_flag=False,
                source_entry_id=None, created_at=now, ladder=rungs,
                origin=self.BORROWED + ",".join(bases)))
        return {"added": added, "skipped": skipped}

    @classmethod
    def borrowed_bases(cls, origin: str) -> list:
        """`origin` → 它跨了哪幾個 base（非借來的回空）。"""
        o = origin or ""
        return [b for b in o[len(cls.BORROWED):].split(",") if b] if o.startswith(cls.BORROWED) else []

    def delete_why_node(self, wid: int, now: str = "") -> bool:
        """**封存**一條理解（spec 055）——不再硬刪。

        ⚠️ **不清 embedding**：檢索一律先過 `list_corpus_entries`，那裡已經濾掉封存的
        ⇒ 清它是多餘的，而且**弄壞復原**（向量沒了要重算一次 API，還不會報錯）。
        向量在**抹除**時才清（spec 056 FR-008）。
        """
        from datetime import datetime, timezone
        now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = self.conn.execute(
            f"UPDATE why_nodes SET archived_at=%s WHERE {self._OWN} AND id=%s AND {self._LIVE}", (now, wid))
        self.conn.commit()
        return cur.rowcount > 0

    # --- Articles（知識的輸出，階段 30）：生成文章存檔（輸出物、不回灌場）---
    def save_article(self, topic: str, title: str, markdown: str,
                     length: str = "", level: str = "", created_at: str = "",
                     root_ids: list | None = None, ext_ids: list | None = None,
                     conversation_id: int | None = None) -> int:
        """存文章。spec 049：**連結也落庫**——用了哪些核心理解、從哪段對話生的。

        ⚠️ 在此之前 `articles` 的連結欄是空的：References 是生成時算出來寫進 markdown
        **字串**的，那是文字不是連結 ⇒ 搬文章時系統不知道它跟什麼糾纏，
        而那**不會顯示成「沒關係」，會顯示成「沒問題」**。
        """
        aid = self._insert_id(
            f"INSERT INTO articles (topic, title, markdown, length, level, created_at,"
            f" conversation_id, owner_id, persona_id) VALUES (%s,%s,%s,%s,%s,%s,%s,{self.owner},{self._P})",
            (topic, title, markdown, length, level, created_at, conversation_id))
        for layer, ids in (("body", root_ids or []), ("ext", ext_ids or [])):
            for wid in ids:
                self.conn.execute(
                    "INSERT INTO article_roots (article_id, why_node_id, layer)"
                    " VALUES (%s,%s,%s)", (aid, int(wid), layer))
        self.conn.commit()
        return aid

    def article_roots(self, aid: int) -> list[int]:
        """這篇文章用到的核心理解 id（正文＋延伸）。"""
        return [int(r["why_node_id"]) for r in self.conn.execute(
            "SELECT why_node_id FROM article_roots WHERE article_id=%s ORDER BY why_node_id",
            (aid,))]

    def list_articles(self) -> list[dict]:
        """列已存文章（不含全文，新在上）。"""
        return [dict(r) for r in self.conn.execute(
            f"SELECT id, topic, title, length, level, created_at FROM articles"
            f" WHERE {self._OWN} AND {self._LIVE} ORDER BY id DESC")]

    def get_article(self, aid: int) -> dict | None:
        r = self.conn.execute(f"SELECT * FROM articles WHERE {self._OWN} AND id=%s", (aid,)).fetchone()
        return dict(r) if r else None

    def delete_article(self, aid: int, now: str = "") -> bool:
        """**封存**一份應用（spec 055）——不再硬刪。"""
        from datetime import datetime, timezone
        now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = self.conn.execute(
            f"UPDATE articles SET archived_at=%s WHERE {self._OWN} AND id=%s AND {self._LIVE}", (now, aid))
        self.conn.commit()
        return cur.rowcount > 0

    # --- 領域樹（spec 048）：領域＝節點、主題 Topic＝從根到節點的路徑 ---
    # ⚠️ **路徑不存**，一律由 `parent_id` 導出。存一份路徑字串的話，改名／搬家就要全量重算，
    # 而**漏算不會報錯**——只會讓路徑慢慢對不上。這是「節點與路徑分得開」的實作形態。
    def create_domain(self, name: str, parent_id: int | None = None) -> int:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cid = self._insert_id(
            f"INSERT INTO domains (name, parent_id, created_at, owner_id, persona_id)"
            f" VALUES (%s,%s,%s,{self.owner},{self._P})",
            (name.strip(), parent_id, now))
        self.conn.commit()
        return cid

    def list_domains(self) -> list[dict]:
        """**活的**領域樹。⚠️ 已封存的不在裡面——遺骸不是位置（spec 055 FR-003）。"""
        return [dict(r) for r in self.conn.execute(
            f"SELECT id, name, parent_id, created_at FROM domains"
            f" WHERE {self._OWN} AND {self._LIVE} ORDER BY id")]

    def rename_domain(self, did: int, name: str) -> None:
        self.conn.execute(f"UPDATE domains SET name=%s WHERE {self._OWN} AND id=%s", (name.strip(), did))
        self.conn.commit()

    def domain_path(self, did: int) -> list[dict]:
        """從根到這個領域的序列（＝主題 Topic）。回 [{id, name}, …]，根在前。"""
        rows = {d["id"]: d for d in self.list_domains()}
        out, cur, seen = [], did, set()
        while cur is not None and cur in rows and cur not in seen:
            seen.add(cur)                      # 防禦：資料若已成環也不會無窮迴圈
            out.append({"id": cur, "name": rows[cur]["name"]})
            cur = rows[cur]["parent_id"]
        return list(reversed(out))

    # ── 出生就歸位（spec 051）：只看出處，**不看內容** ──────────────────
    # ⚠️ 這跟已被否決四次的「自動分類」的差別在**依據**，不在準確度：
    # 自動分類是 AI 看內容猜；這裡是「它長自一段你已經放好位置的東西」＝溯源事實。
    # 判準：**它錯的時候，是你把出處放錯了，不是模型猜錯了。**

    def lca_domain(self, domains: list) -> int | None:
        """一組出處領域的**最近共同祖先**。回 None ＝ 根領域／沒有訊號。

        ⚠️ `None` 的出處**不算一票**（FR-005）：它說的是「我還沒被放過」，
        不是「答案是根」。不然一條沒歸位的出處就會把答案全部拉回根，
        而那會讓這一刀在 backlog 清空前**幾乎永遠不生效**。
        （同 spec 050 FR-007 的同一個區分：根是可以站的位置，但它表示「還沒放過」。）
        """
        known = [d for d in domains if d is not None]
        if not known:
            return None
        paths = [[p["id"] for p in self.domain_path(d)] for d in known]
        if any(not p for p in paths):          # 領域已被刪掉 → 沒有可信的共同祖先
            return None
        common = None
        for i in range(min(len(p) for p in paths)):
            here = paths[0][i]
            if all(p[i] == here for p in paths):
                common = here
            else:
                break
        return common

    def inherited_domain(self, parent_domains: list, current: int | None) -> int | None:
        """新知識該落在哪：**有出處就繼承出處，沒有就用你站的地方**（FR-006）。

        ⚠️ 出處**勝過**當前領域——出處是事實，站的地方只是預設值。
        """
        return self.lca_domain(parent_domains) or current

    # ── 一個領域的視野（spec 052）──────────────────────────────────────
    # ⚠️ 這裡的 `scope` 是**子樹**（含自己與所有子孫），不是單一節點
    # ——使用者的裁決：「當前領域含子領域」⇒ **站在根＝看到全部**。

    def domain_scope(self, did: int | None) -> set[int] | None:
        """立足點的子樹。回 `None` ＝ 根領域＝**整個知識庫**（不設限）。"""
        return None if did is None else self.domain_descendants(did)

    def domain_view(self, did: int | None) -> dict:
        """站在 `did` 看到的東西：直屬子領域 ＋ 子樹裡的葉節點 ＋ **通往外面**的連結。

        ⚠️ **「通往外面」相對於立足點**（FR-003）：一條邊的兩端都在我的子樹裡就不算。
        同一條 `Flow Matching → 數學` 的邊，站在 Flow Matching 是跨出去、站在 AI 是內部連結
        ——**糾纏是 `(邊, 立足點)` 的屬性，不是那條邊的固有屬性**。
        把它當成固有屬性的話，站在祖先會看到一堆其實在自己家裡的「外部連結」。
        """
        scope = self.domain_scope(did)
        # ⚠️ 站在專案裡就看專案的；站在**別處（含根）就完全不看**。
        #    使用者：「不要把開發模式的來源歸換在互動模式的裡面」——
        #    三個專案 514 件東西會把他自己的 9 件擠掉，而那是他實際撞到的。
        projects = self.project_domain_ids()
        hide = set() if (scope is not None and (scope & projects)) else projects
        rows = [r for r in self._inventory_rows() if r["domain_id"] not in hide]
        # 每個子領域**含子孫**有幾件——側欄的數字要跟「點進去之後看到的」一致，
        # ⚠️ 否則那個數字就是在說謊，而說謊的數字比沒有數字更糟。
        children = []
        for d in self.list_domains():
            # ⚠️ 子領域也要照同一條線——不然「領域」那一格會列出專案，
            #    而它底下的東西在別格看不到，數字對不起來。
            if d["parent_id"] != did or d["id"] in hide:
                continue
            sub = self.domain_descendants(d["id"])
            children.append({**d, "count": sum(1 for r in rows if r["domain_id"] in sub)})

        items, outward, seen = [], [], set()
        for row in rows:
            inside = scope is None or (row["domain_id"] in scope)
            if not inside:
                continue
            items.append(row)
            if scope is None:
                continue                      # 站在根：沒有「外面」可言
            for nk, nref in self._neighbours(row["kind"], row["ref"]):
                nd = self.knowledge_domain(nk, nref)
                # ⚠️ 對方在根領域 ＝ 還沒被放過，不是「在外面」（同 spec 050 FR-007／051 FR-005）
                if nd is None or nd in scope:
                    continue
                key = (nk, str(nref))
                if key in seen:
                    continue
                seen.add(key)
                outward.append({"kind": nk, "ref": nref, "domain_id": nd})
        return {"children": children, "items": items, "outward": outward,
                "path": [] if did is None else self.domain_path(did)}

    def _inventory_rows(self) -> list[dict]:
        """四種知識的扁平清冊（整理台與領域視野共用一份定義）。

        `at`＝那件東西的時間（spec 057：檔案總管要有「更新時間」欄才排得了序）。
        ⚠️ 四種的時間欄名字**不一樣**——對話用最後活動、來源用收進日、其餘用建立日。
        假設它們同名的話，缺的那幾種會安靜地排在最後面。
        """
        out = []
        for r in self.conn.execute(
                f"SELECT id, title, domain_id,"
                f" COALESCE(NULLIF(last_activity_at,''), created_at, '') AS at"
                f" FROM conversations WHERE {self._OWN} AND {self._LIVE} ORDER BY id DESC"):
            out.append({"kind": "conversation", "ref": r["id"],
                        "label": r["title"] or "未命名", "domain_id": r["domain_id"],
                        "at": r["at"] or ""})
        for r in self.conn.execute(
                f"SELECT id, claim, domain_id, COALESCE(created_at,'') AS at FROM why_nodes"
                f" WHERE {self._OWN} AND status='anointed' AND {self._LIVE} ORDER BY id DESC"):
            out.append({"kind": "why_node", "ref": r["id"],
                        "label": (r["claim"] or "")[:80], "domain_id": r["domain_id"],
                        "at": r["at"] or ""})
        for r in self.conn.execute(
                f"SELECT id, topic, title, domain_id, COALESCE(created_at,'') AS at FROM articles"
                f" WHERE {self._OWN} AND {self._LIVE} ORDER BY id DESC"):
            out.append({"kind": "article", "ref": r["id"],
                        "label": r["title"] or r["topic"] or "未命名",
                        "domain_id": r["domain_id"], "at": r["at"] or ""})
        for r in self.conn.execute(
                f"SELECT url, MIN(title) AS title, MIN(domain_id) AS domain_id,"
                f" MAX(COALESCE(ingested_at,'')) AS at"
                f" FROM digest_entries WHERE {self._OWN} AND {self._LIVE} GROUP BY url ORDER BY MAX(id) DESC"):
            out.append({"kind": "source", "ref": r["url"],
                        "label": r["title"] or r["url"], "domain_id": r["domain_id"],
                        "at": r["at"] or ""})
        return out

    def place_new(self, kind: str, ref, current: int | None = None) -> int | None:
        """把一件**剛出生**的知識放到它該在的領域，回放到哪。

        出處就是它的**直接鄰居**（`_neighbours`）——所以這一個方法同時服務
        冊封理解／保存文章／收來源三條路徑，不用在每個呼叫點各接一次線。

        ⚠️ **呼叫時機**：必須在**連結都建好之後**。`_do_anoint` 是先冊封、
        後才把對話連上去的 ⇒ 太早呼叫的話 `_neighbours` 是空的，
        東西會安靜地落在根領域，而且看起來跟「本來就沒出處」一模一樣。
        """
        parents = [self.knowledge_domain(nk, nref) for nk, nref in self._neighbours(kind, ref)]
        did = self.inherited_domain(parents, current)
        if did is not None:
            self.set_knowledge_domain(kind, ref, did)
        return did

    def domain_descendants(self, did: int) -> set[int]:
        """這個領域的所有子孫（含自己）。用於擋成環。"""
        children: dict[int, list[int]] = {}
        for d in self.list_domains():
            children.setdefault(d["parent_id"], []).append(d["id"])
        out, stack = set(), [did]
        while stack:
            n = stack.pop()
            if n in out:
                continue
            out.add(n)
            stack.extend(children.get(n, []))
        return out

    # ══ 封存（spec 055）：**離開活的場，留下遺骸** ══════════════════════
    # 使用者的比喻：超新星爆炸 · 黑洞 · 細胞凋亡——共同點是**結束不等於湮滅**。
    # 它是**一個通用動作**，領域與四種知識都適用。
    #
    # ⚠️ 唯一會沉默失敗的地方：**封存必須擋住檢索，不只擋住畫面**。
    # 只在清單頁過濾、沒擋住 `list_attractors`／`list_seeds` 的話，
    # 封存過的知識**仍在影響每一個回答**，而且沒有任何跡象。
    _LIVE = "COALESCE(archived_at,'')='' AND COALESCE(erased_at,'')=''"

    def _own(self, alias: str = "") -> str:
        """誰看得到這一列。⚠️ **owner 與 persona 共用同一個述詞**——

        這樣 88 個查詢點自動涵蓋 persona，不需要為了隱私再改一次那 88 個地方。
        `persona_id IS NULL` ＝ **共用**（spec 067）：**預設共用，隔離是選擇**，
        反過來會讓場碎掉，而北極星第一條是「給你意外的連結」。
        ⚠️ **沒有「看全部」模式**——有後門就不是硬隔離。
        """
        pf = f"{alias}." if alias else ""
        if self.persona is None:
            return f"({pf}owner_id={self.owner} AND {pf}persona_id IS NULL)"
        return (f"({pf}owner_id={self.owner} AND"
                f" ({pf}persona_id IS NULL OR {pf}persona_id={self.persona}))")
    @classmethod
    def _live(cls, alias: str = "") -> str:
        """`_LIVE` 的別名版。⚠️ **一份寫法**——兩套會漂，而漂掉的那一套不會報錯。"""
        p = f"{alias}." if alias else ""
        return f"COALESCE({p}archived_at,'')='' AND COALESCE({p}erased_at,'')=''"

    _ERASED = "COALESCE(erased_at,'')<>''"
    # 抹除時要清空的內容欄（**位址欄不動**：`digest_entries.url` 是位址不是內容，
    # 抹掉它疤就找不到了——而疤存在的意義就是「這裡曾經有東西」問得出來）。
    _ERASE_FIELDS = {
        "why_node": [("claim", "''"), ("evidence_urls", "'[]'"), ("ladder", "'[]'"),
                     ("touchstones", "'[]'"), ("source_quote", "''")],
        "article": [("topic", "''"), ("title", "''"), ("markdown", "''")],
        "conversation": [("title", "''"), ("messages", "'[]'"), ("chapters", "'[]'")],
        "source": [("title", "''"), ("article_body", "''"), ("article_headline", "''"),
                   ("note", "''")],
    }

    def archive_knowledge(self, kind: str, ref, now: str, root: int | None = None) -> None:
        """封存一則知識。`root`＝被哪個領域的封存連帶帶走的（None＝自己被封的）。"""
        t, k = self._KIND_TABLE[kind]
        self.conn.execute(
            f"UPDATE {t} SET archived_at=%s, archived_root=%s WHERE {self._OWN} AND {k}=%s", (now, root, ref))
        self.conn.commit()

    def restore_knowledge(self, kind: str, ref) -> None:
        st = self._archived_state(kind, ref)
        if st and st[1]:
            raise ValueError("這件東西已經被抹除了，救不回來")   # 第二次的死（FR-003）
        t, k = self._KIND_TABLE[kind]
        self.conn.execute(
            f"UPDATE {t} SET archived_at='', archived_root=NULL WHERE {self._OWN} AND {k}=%s", (ref,))
        self.conn.commit()

    def archived_items(self) -> list[dict]:
        """遺骸：封存過的知識（是什麼、什麼時候封的、被誰連帶帶走的）。"""
        out = []
        for kind, (t, k) in self._KIND_TABLE.items():
            label = {"conversation": "title", "why_node": "claim",
                     "article": "title", "source": "title"}[kind]
            grp = " GROUP BY url" if kind == "source" else ""
            sel = (f"SELECT {k} AS ref, MIN({label}) AS label, MIN(archived_at) AS archived_at,"
                   f" MIN(archived_root) AS archived_root FROM {t} WHERE {self._OWN}"
                   f" AND COALESCE(archived_at,'')<>'' AND NOT ({self._ERASED}){grp}"
                   ) if kind == "source" else (
                   f"SELECT {k} AS ref, {label} AS label, archived_at, archived_root FROM {t} WHERE {self._OWN}"
                   f" AND COALESCE(archived_at,'')<>'' AND NOT ({self._ERASED})")
            for r in self.conn.execute(sel):
                out.append({"kind": kind, "ref": r["ref"], "label": (r["label"] or "")[:80],
                            "archived_at": r["archived_at"],
                            "archived_root": r["archived_root"]})
        return sorted(out, key=lambda x: x["archived_at"], reverse=True)

    # ── 第二次的死（spec 056）：抹除，只留一塊疤 ─────────────────────
    # ⚠️ **抹除只作用在遺骸上**——活的東西沒有任何單一動作能一次消失。
    # 這不是多一道確認視窗（那是劇場），是**路徑上真的沒有捷徑**。

    def _archived_state(self, kind: str, ref) -> tuple[str, str] | None:
        t, k = self._KIND_TABLE[kind]
        r = self.conn.execute(
            f"SELECT COALESCE(archived_at,'') AS a, COALESCE(erased_at,'') AS e"
            f" FROM {t} WHERE {self._OWN} AND {k}=%s", (ref,)).fetchone()
        return (r["a"], r["e"]) if r else None

    def erase_knowledge(self, kind: str, ref, now: str) -> None:
        """**第二次的死**：內容全空、記下時間，**列還在**。

        ⚠️ 只接受**已封存**的目標（FR-001）。活的東西要先經過第一次的死。
        """
        st = self._archived_state(kind, ref)
        if st is None:
            raise ValueError("找不到這件東西")
        if not st[0]:
            raise ValueError("要先封存才能抹除——活的東西不能一步消失")
        t, k = self._KIND_TABLE[kind]
        sets = ", ".join(f"{c}={v}" for c, v in self._ERASE_FIELDS[kind])
        self.conn.execute(
            f"UPDATE {t} SET {sets}, erased_at=%s WHERE {self._OWN} AND {k}=%s", (now, ref))
        # 內容都不在了，向量留著就是幽靈（FR-008）
        if kind == "why_node":
            self.conn.execute("DELETE FROM entry_embeddings WHERE entry_id=%s", (-int(ref),))
        elif kind == "source":
            for r in self.conn.execute(
                    f"SELECT id FROM digest_entries WHERE {self._OWN} AND url=%s", (ref,)).fetchall():
                self.conn.execute(
                    "DELETE FROM entry_embeddings WHERE entry_id=%s", (int(r["id"]),))
        self.conn.commit()

    def erase_domain(self, did: int, now: str) -> None:
        """抹除一個領域遺骸。

        ⚠️ **MUST NOT 連帶抹除它底下的遺骸內容**（FR-005）——不做第二次死的串聯。
        那些內容改掛到根領域底下，仍可**單獨**復原：它們原本的位置已經沒有名字了。
        """
        r = self.conn.execute(
            f"SELECT COALESCE(archived_at,'') AS a FROM domains WHERE {self._OWN} AND id=%s", (did,)).fetchone()
        if r is None:
            raise ValueError("找不到這個領域")
        if not r["a"]:
            raise ValueError("要先封存才能抹除——活的領域不能一步消失")
        for kind, (t, k) in self._KIND_TABLE.items():
            self.conn.execute(
                f"UPDATE {t} SET domain_id=NULL, archived_root=NULL"
                f" WHERE {self._OWN} AND (domain_id=%s OR archived_root=%s)", (did, did))
        self.conn.execute(
            "UPDATE domains SET name='', archived_root=NULL, archived_from=NULL,"
            f" erased_at=%s WHERE {self._OWN} AND id=%s", (now, did))
        self.conn.commit()

    def scar(self, kind: str, ref) -> dict | None:
        """疤：這裡曾經有東西，什麼時候被抹掉的。活的（或只是封存的）→ None。"""
        st = self._archived_state(kind, ref)
        if st is None or not st[1]:
            return None
        return {"kind": kind, "ref": ref, "erased_at": st[1]}

    def pointers_to(self, kind: str, ref) -> list[dict]:
        """誰指著它——抹除前要說出來（FR-004）。

        ⚠️ 這個專案被同一件事咬過：把明顯壞掉的指標**變成自信地指錯的指標**。
        所以抹除前先把它們攤開，讓人自己決定。
        """
        return [{"kind": nk, "ref": nref} for nk, nref in self._neighbours(kind, ref)]

    def archive_domain_preview(self, did: int) -> dict:
        """封存這個領域**會帶走什麼**：整棵子樹的知識件數與子領域數。

        ⚠️ 這裡跟糾纏的「只算直接連結」相反，而理由是同一條：**報告要對得上實際行為**。
        既然整棵子樹會被帶走，報少了才是嚇人——使用者會以為只封一層。
        """
        sub = self.domain_descendants(did)
        return {"items": sum(1 for r in self._inventory_rows() if r["domain_id"] in sub),
                "children": len(sub) - 1,
                "to": self._parent_of(did)}

    def _parent_of(self, did: int) -> int | None:
        r = self.conn.execute(f"SELECT parent_id FROM domains WHERE {self._OWN} AND id=%s", (did,)).fetchone()
        return r["parent_id"] if r else None

    def archive_domain(self, did: int, now: str) -> dict:
        """封存一個領域：**整棵子樹一起成為遺骸**（使用者裁決 2026-08-26）。

        ⚠️ 知識**不上移到父領域**——它們跟著容器一起離開活的場，之後可以一起回來。
        （階段 49 原本是上移；使用者把它改成連帶封存，因為「不見」的不該只有容器。）
        """
        moved = self.archive_domain_preview(did)
        sub = self.domain_descendants(did)
        marks = ",".join(["%s"] * len(sub))
        for kind, (t, k) in self._KIND_TABLE.items():
            self.conn.execute(
                f"UPDATE {t} SET archived_at=%s, archived_root=%s"
                f" WHERE {self._OWN} AND domain_id IN ({marks}) AND {self._LIVE}", (now, did, *sub))
        self.conn.execute(
            f"UPDATE domains SET archived_at=%s, archived_root=%s"
            f" WHERE {self._OWN} AND id IN ({marks}) AND {self._LIVE}", (now, did, *sub))
        self.conn.execute(
            f"UPDATE domains SET archived_from=parent_id WHERE {self._OWN} AND id=%s", (did,))
        self.conn.commit()
        return moved

    def archived_domains(self) -> list[dict]:
        """遺骸：封存過的領域（名字、原本的父領域、封存時間）。"""
        return [dict(r) for r in self.conn.execute(
            f"SELECT id, name, archived_at, archived_from, archived_root FROM domains"
            f" WHERE {self._OWN} AND COALESCE(archived_at,'')<>'' AND NOT ({self._ERASED})"
            f" ORDER BY archived_at DESC")]

    def restore_domain(self, did: int) -> None:
        """復原：把**同一批**（`archived_root = did`）一起帶回原位。

        ⚠️ 只復原同一批——自己先被單獨封存過的東西**不該搭順風車回來**，
        那會把使用者的另一個決定一起撤銷掉。
        """
        for kind, (t, k) in self._KIND_TABLE.items():
            self.conn.execute(
                f"UPDATE {t} SET archived_at='', archived_root=NULL WHERE {self._OWN} AND archived_root=%s", (did,))
        self.conn.execute(
            f"UPDATE domains SET archived_at='', archived_root=NULL WHERE {self._OWN} AND archived_root=%s", (did,))
        self.conn.execute(
            "UPDATE domains SET parent_id=COALESCE(archived_from, parent_id), archived_from=NULL"
            f" WHERE {self._OWN} AND id=%s", (did,))
        self.conn.commit()

    def move_domain(self, did: int, new_parent: int | None) -> None:
        """搬動領域。⚠️ **擋成環**——把節點搬到自己的子孫底下，路徑計算不會報錯，
        只會變成無意義的結果（FR-004）。"""
        if new_parent is not None and new_parent in self.domain_descendants(did):
            raise ValueError("不能把領域搬到它自己或它的子孫底下（會成環）")
        self.conn.execute(f"UPDATE domains SET parent_id=%s WHERE {self._OWN} AND id=%s", (new_parent, did))
        self.conn.commit()

    def set_conversation_domain(self, cid: int, domain_id: int | None) -> None:
        self.conn.execute(f"UPDATE conversations SET domain_id=%s WHERE {self._OWN} AND id=%s", (domain_id, cid))
        self.conn.commit()

    # --- 糾纏 Tangle（spec 049）：樹裝不下的那條連結 ---
    # ⚠️ 糾纏**在整理之前就存在**——整理只是讓它現形。所以這裡是**查既有連結**，不是建東西。
    #
    # 兩條防爆界線（違反任一條，這功能第二次就沒人用）：
    # ① **只算直接連結**，不算傳遞閉包。66/75 條理解連著對話，搬一段跳 15 條詢問＝廢。
    # ② **連帶只走一層**，不遞迴。知識的連結是**網不是樹**，不設界線會搬走半個場。
    # spec 050：`kind → (表, 鍵欄位)`。
    # ⚠️ 來源打破了「身分＝整數 id」的形狀：一個「來源」＝**一個 url ＝多個 digest_entries 塊**
    # （`list_source_groups` 就是 `GROUP BY de.url`）。所以它的鍵是 url，設領域時整組塊一起設。
    # 否決用 `MIN(id)` 當代表——那是一個會隨新增塊漂移的主鍵。
    _KIND_TABLE = {
        "conversation": ("conversations", "id"),
        "why_node": ("why_nodes", "id"),
        "article": ("articles", "id"),
        "source": ("digest_entries", "url"),
    }

    def knowledge_domain(self, kind: str, ref) -> int | None:
        t, k = self._KIND_TABLE[kind]
        r = self.conn.execute(
            f"SELECT domain_id FROM {t} WHERE {self._OWN} AND {k}=%s", (ref,)).fetchone()
        return r["domain_id"] if r else None

    def set_knowledge_domain(self, kind: str, ref, domain_id: int | None,
                             by: str = "human") -> None:
        """把一件知識放到某個領域。`by`＝`human`（你放的）｜`machine`（劃界算的）。

        ⚠️ spec 069：**人的 override 要看得出來**——分不出來的話，
        你會把機器的猜測當成自己的判斷。預設是 `human`，因為呼叫這支的多半是人的動作。
        """
        t, k = self._KIND_TABLE[kind]
        # 來源時 `k='url'` ⇒ 這一句會套到該 url 的**所有塊**，那正是要的（FR-008）。
        self.conn.execute(f"UPDATE {t} SET domain_id=%s, assigned_by=%s"
                          f" WHERE {self._OWN} AND {k}=%s", (domain_id, by, ref))
        self.conn.commit()

    def _neighbours(self, kind: str, ref) -> list[tuple[str, object]]:
        """這個知識**直接**連著誰（一層，不遞迴）。"""
        out: list[tuple[str, object]] = []
        if kind == "conversation":
            out += [("why_node", int(r["id"])) for r in self.conn.execute(
                f"SELECT id FROM why_nodes WHERE {self._OWN} AND conversation_id=%s", (ref,))]
            out += [("article", int(r["id"])) for r in self.conn.execute(
                f"SELECT id FROM articles WHERE {self._OWN} AND conversation_id=%s", (ref,))]
            r = self.conn.execute(
                f"SELECT carried_kind, carried_ref FROM conversations WHERE {self._OWN} AND id=%s", (ref,)).fetchone()
            if r and r["carried_kind"] == "source" and r["carried_ref"]:
                out.append(("source", r["carried_ref"]))
            elif r and r["carried_kind"] == "article" and str(r["carried_ref"]).isdigit():
                out.append(("article", int(r["carried_ref"])))
        elif kind == "why_node":
            r = self.conn.execute(
                f"SELECT conversation_id, source_entry_id FROM why_nodes WHERE {self._OWN} AND id=%s", (ref,)).fetchone()
            if r and r["conversation_id"]:
                out.append(("conversation", int(r["conversation_id"])))
            # ⚠️ `source_entry_id` **預設 0 不是 NULL**——`IS NOT NULL` 在這裡恆真。
            if r and (r["source_entry_id"] or 0) > 0:
                e = self.conn.execute(
                    f"SELECT url FROM digest_entries WHERE {self._OWN} AND id=%s", (r["source_entry_id"],)).fetchone()
                if e and e["url"]:
                    out.append(("source", e["url"]))
            out += [("article", int(x["article_id"])) for x in self.conn.execute(
                "SELECT article_id FROM article_roots WHERE why_node_id=%s", (ref,))]
        elif kind == "article":
            out += [("why_node", int(x["why_node_id"])) for x in self.conn.execute(
                "SELECT why_node_id FROM article_roots WHERE article_id=%s", (ref,))]
            r = self.conn.execute(
                f"SELECT conversation_id FROM articles WHERE {self._OWN} AND id=%s", (ref,)).fetchone()
            if r and r["conversation_id"]:
                out.append(("conversation", int(r["conversation_id"])))
        elif kind == "source":
            out += [("why_node", int(x["id"])) for x in self.conn.execute(
                "SELECT wn.id AS id FROM why_nodes wn JOIN digest_entries de"
                f" ON wn.source_entry_id=de.id WHERE {self._own('wn')} AND de.url=%s AND wn.source_entry_id>0", (ref,))]
            out += [("conversation", int(x["id"])) for x in self.conn.execute(
                f"SELECT id FROM conversations WHERE {self._OWN} AND carried_kind='source' AND carried_ref=%s", (ref,))]
        return out

    # ── 批次（spec 050）：單件操作＝一個元素的清單，不另留一套 ──────────────

    def batch_tangles(self, items, new_domain: int | None) -> list[dict]:
        """把 `items` 整批搬到 `new_domain` 之後，**會被拆散**的直接鄰居（去重）。

        ⚠️ 判準是「**搬完之後**兩端是否不同域」，不是「現在」。
        ⇒ **同批成員之間不算糾纏**——一起搬的東西沒有被拆散（FR-003）。
        ⚠️ 鄰居在**根領域**（`domain_id IS NULL`）時不算糾纏（FR-007）。
        理由：**糾纏是「兩件你刻意放過的東西被拆散」**，而根領域是東西**還沒被放過**的地方。
        若把根也算成一個位置，那麼「把第一件東西搬出根」就會對它所有的鄰居報糾纏
        ——75 條理解裡 66 條連著對話，第一次整理就跳十幾條詢問，那功能第二次沒人用。
        """
        moving = {(k, str(r)) for k, r in items}
        seen: set[tuple[str, str]] = set()
        out: list[dict] = []
        for kind, ref in items:
            for nk, nref in self._neighbours(kind, ref):     # 一層，不是閉包（FR-005）
                key = (nk, str(nref))
                if key in moving or key in seen:
                    continue
                d = self.knowledge_domain(nk, nref)
                if d is not None and d != new_domain:
                    seen.add(key)
                    out.append({"kind": nk, "ref": nref, "domain_id": d})
        return out

    def batch_move(self, items, new_domain: int | None,
                   bring_along: bool = False, by: str = "human") -> list[dict]:
        """整批搬。`bring_along` ＝ 把被拆散的直接鄰居也搬過去（⚠️ 只一層，FR-006）。"""
        tangles = self.batch_tangles(items, new_domain)
        for kind, ref in items:
            self.set_knowledge_domain(kind, ref, new_domain, by=by)
        if bring_along:
            for t in tangles:      # ⚠️ 只搬這一層，不對它們再遞迴
                self.set_knowledge_domain(t["kind"], t["ref"], new_domain, by=by)
        return tangles

    # --- 譯文快取（spec 039）：**逐翻譯單位**，不是逐文件 ---
    # ⚠️ 為什麼是逐單位：一份 45 個單位的來源，只要有 1 個降級，逐文件快取就一個字都不能存
    #（FR-006）。真跑實測 colah 那篇就是 45 取 1，機率上 (1-p)^45 讓逐文件快取多半落空
    # ——那等於使用者要的「自動保存」大部分時候不會發生。逐單位則：成功的存、失敗的永遠重試，
    # FR-006 的**理由**（不把失敗固定下來）反而被更完整地滿足。
    def get_translation_units(self, keys: list[str], now: str) -> dict[str, str]:
        """回 {unit_key: 譯文}，只含命中的；順手把命中的續命（讀取即續命）。"""
        if not keys:
            return {}
        marks = ",".join(["%s"] * len(keys))
        rows = self.conn.execute(
            f"SELECT unit_key, markdown FROM translation_units WHERE unit_key IN ({marks})",
            tuple(keys)).fetchall()
        hit = {r["unit_key"]: r["markdown"] for r in rows}
        if hit:
            hm = ",".join(["%s"] * len(hit))
            self.conn.execute(
                f"UPDATE translation_units SET last_used_at=%s WHERE unit_key IN ({hm})",
                (now, *hit.keys()))
            self.conn.commit()
        return hit

    def save_translation_units(self, pairs: list[tuple[str, str]], now: str) -> None:
        """寫入或覆蓋若干 (unit_key, 譯文)。⚠️ 呼叫端只能傳**翻譯成功**的單位（FR-006）。"""
        for key, md in pairs:
            self.conn.execute(
                "INSERT INTO translation_units (unit_key, markdown, last_used_at)"
                " VALUES (%s,%s,%s)"
                " ON CONFLICT(unit_key) DO UPDATE SET markdown=excluded.markdown,"
                " last_used_at=excluded.last_used_at",
                (key, md, now))
        self.conn.commit()

    def purge_stale_translations(self, before: str) -> int:
        """刪除 last_used_at < before 的譯文單位，回刪除數（FR-005）。

        完全自動、沒有任何使用者介面——譯文能重生，清掉的代價只是下次要再翻一次。
        """
        rows = self.conn.execute(
            "SELECT unit_key FROM translation_units WHERE last_used_at < %s", (before,)).fetchall()
        if rows:
            self.conn.execute(
                "DELETE FROM translation_units WHERE last_used_at < %s", (before,))
            self.conn.commit()
        return len(rows)

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
                f"SELECT id, messages FROM conversations WHERE {self._OWN} ORDER BY id ASC").fetchall():
            if conversation_fingerprint(json.loads(r["messages"] or "[]")) == fp:
                cid = r["id"]          # 同段已存→共用（不插入、不刪改既有）
                break
        if cid is None:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            cid = self._insert_id(
                f"INSERT INTO conversations (title, messages, why_node_id, created_at, owner_id, persona_id)"
                f" VALUES (%s,%s,%s,%s,{self.owner},{self._P})",
                (title, json.dumps(messages, ensure_ascii=False), why_node_id, now))
        if why_node_id is not None:    # 連結存 why_node 側（事實來源）
            self.conn.execute(
                f"UPDATE why_nodes SET conversation_id=%s WHERE {self._OWN} AND id=%s", (cid, why_node_id))
        self.conn.commit()
        return cid

    def _row_to_conversation(self, r):
        from ..models import Conversation
        keys = r.keys()
        return Conversation(
            id=r["id"], title=r["title"] or "",
            messages=json.loads(r["messages"] or "[]"),
            why_node_id=r["why_node_id"], created_at=r["created_at"] or "",
            temporary=bool(r["temporary"]) if "temporary" in keys else False,
            last_activity_at=(r["last_activity_at"] if "last_activity_at" in keys else "")
            or (r["created_at"] or ""),
            chapters=json.loads((r["chapters"] if "chapters" in keys else "[]") or "[]"),
            domain_id=(r["domain_id"] if "domain_id" in keys else None))

    def set_conversation_chapters(self, cid: int, chapters: list) -> None:
        """存切好的章節（階段29 持久化，避免每次檢視重切）。"""
        self.conn.execute(
            f"UPDATE conversations SET chapters=%s WHERE {self._OWN} AND id=%s",
            (json.dumps(chapters, ensure_ascii=False), cid))
        self.conn.commit()

    _CONV_COLS = ("id, title, messages, why_node_id, created_at, temporary,"
                  " last_activity_at, chapters, domain_id")

    def list_conversations(self) -> list:
        rows = self.conn.execute(
            f"SELECT {self._CONV_COLS} FROM conversations"
            f" WHERE {self._OWN} AND {self._LIVE} ORDER BY id DESC").fetchall()
        return [self._row_to_conversation(r) for r in rows]

    def get_conversation(self, cid: int):
        r = self.conn.execute(
            f"SELECT {self._CONV_COLS} FROM conversations WHERE {self._OWN} AND id=%s", (cid,)).fetchone()
        return self._row_to_conversation(r) if r else None

    # --- 暫時存檔＋TTL 衰減（spec 028）---
    def autosave_temporary(self, temp_id, messages: list, now: str,
                           carried_kind: str = "", carried_ref: str = "",
                           domain_id: int | None = None):
        """自動存（每輪 upsert 一筆）。空→None。temp_id 存在→**就地更新同一筆**（永久維持永久、暫存維持暫存
        ——接回已存檔對話繼續聊時不再另開暫存）；查無 id→新建暫存。回 id。

        `carried_kind`／`carried_ref`（spec 044）＝這段對話的**由來**：它是帶著哪篇文章／
        哪份來源開的。⚠️ **只在建立那一刻寫，UPDATE 分支一個字都不碰**——
        由來記的是「它從哪來的」，是歷史事實不是當前狀態。
        這讓「不被改寫」成為結構性的（沒有寫入路徑），而不是靠呼叫端自律。
        """
        if not messages:
            return None
        if temp_id:
            cur = self.conn.execute(
                f"UPDATE conversations SET messages=%s, last_activity_at=%s WHERE {self._OWN} AND id=%s",
                (json.dumps(messages, ensure_ascii=False), now, temp_id))
            if cur.rowcount > 0:
                self.conn.commit()
                return int(temp_id)
        from ..chat.capture import cheap_title
        cid = self._insert_id(
            "INSERT INTO conversations (title, messages, why_node_id, created_at,"
            f" temporary, last_activity_at, carried_kind, carried_ref, domain_id, owner_id, persona_id)"
            f" VALUES (%s,%s,%s,%s,1,%s,%s,%s,%s,{self.owner},{self._P})",
            (cheap_title(messages), json.dumps(messages, ensure_ascii=False), None, now, now,
             carried_kind or "", carried_ref or "", domain_id))
        self.conn.commit()
        return cid

    def touch_conversation(self, cid: int, now: str) -> bool:
        """接回時重設計時（更新 last_activity_at）。"""
        cur = self.conn.execute(
            f"UPDATE conversations SET last_activity_at=%s WHERE {self._OWN} AND id=%s", (now, cid))
        self.conn.commit()
        return cur.rowcount > 0

    def promote_conversation(self, cid: int, title: str | None = None,
                             why_node_id: int | None = None) -> bool:
        """設標題／連根因（同一筆、不新增）。

        ⚠️ spec 040 起**不再翻動 `temporary`**——分層已移除。名字保留是因為呼叫端語義未變
        （「存這段」＝給它一個名字），但它不再有「升級」的意思。
        `temporary` 欄位刻意留在 schema：移除的是機制，不是資料。
        """
        touched = False
        if title and title.strip():
            self.conn.execute(f"UPDATE conversations SET title=%s WHERE {self._OWN} AND id=%s",
                              (title.strip(), cid))
            touched = True
        if why_node_id is not None:
            self.conn.execute(
                f"UPDATE why_nodes SET conversation_id=%s WHERE {self._OWN} AND id=%s", (cid, why_node_id))
            touched = True
        self.conn.commit()
        return touched

    def rename_conversation(self, cid: int, title: str) -> bool:
        """改對話標題（spec 027，人按才呼叫）。只動 title 欄。回是否有更新。"""
        title = (title or "").strip()
        if not title:
            return False
        cur = self.conn.execute(
            f"UPDATE conversations SET title=%s WHERE {self._OWN} AND id=%s", (title, cid))
        self.conn.commit()
        return cur.rowcount > 0

    def conversation_yield_counts(self) -> dict[int, int]:
        """{對話 id: 以它為由來的核心理解條數}——**一次** GROUP BY（spec 045）。

        ⚠️ 讀的是 `why_nodes.conversation_id`，那是**事實來源**
        （`save_conversation` 的註解自己寫著「連結存 why_node 側（事實來源）」）。
        `conversations.why_node_id` 只在 `save_conversation(…, why_node_id=…)` 那條路才被填，
        而**冊封走的是 `promote_conversation`，只更新 why_nodes 側** ⇒ 讀舊欄位會漏掉
        2/3（正式庫實測：真的是由來的 12 段，舊欄位只認得 4 段）。

        ⚠️ 判準沿用 `conversation_referrers`（有指向就算，不看 status）——
        同一件事不要在兩個地方給不同答案。
        """
        rows = self.conn.execute(
            f"SELECT conversation_id AS cid, COUNT(*) AS c FROM why_nodes"
            f" WHERE {self._OWN} AND conversation_id IS NOT NULL AND {self._LIVE}"
            f" GROUP BY conversation_id").fetchall()
        return {int(r["cid"]): int(r["c"]) for r in rows}

    def conversation_referrers(self, cid: int) -> list[dict]:
        """哪些核心理解以這段對話為由來（why_node.conversation_id=cid）。
        回 [{id, claim, src_from, src_to}]。

        用於刪除保護（有引用者不可刪，否則溯源斷掉，原則 3），
        ＋ spec 046：讓對話頁標得出**哪幾則已冊封**。
        ⚠️ 舊資料沒有範圍時回 0/0 而不是缺鍵——缺鍵會讓前端拿到 undefined 而靜默算錯。
        """
        return [dict(r) for r in self.conn.execute(
            f"SELECT id, claim, COALESCE(src_from,0) AS src_from, COALESCE(src_to,0) AS src_to"
            f" FROM why_nodes WHERE {self._OWN} AND conversation_id=%s AND {self._LIVE} ORDER BY id", (cid,))]

    def delete_conversation(self, cid: int, now: str = "") -> bool:
        """**封存**一段對話（spec 055）——不再硬刪。回是否封到。"""
        from datetime import datetime, timezone
        now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = self.conn.execute(
            f"UPDATE conversations SET archived_at=%s WHERE {self._OWN} AND id=%s AND {self._LIVE}", (now, cid))
        self.conn.commit()
        return cur.rowcount > 0

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
                f"UPDATE why_nodes SET conversation_id=%s WHERE {self._OWN} AND id=%s", (survivor, wid))
        for cid in plan.delete_ids:
            self.conn.execute(f"DELETE FROM conversations WHERE {self._OWN} AND id=%s", (cid,))
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
            f" WHERE {self._own('w')} AND w.conversation_id IS NOT NULL"
            # spec 055：封存過的**兩側**都不算活的由來
            " AND COALESCE(w.archived_at,'')='' AND COALESCE(c.archived_at,'')=''").fetchall():
            out[r["wid"]] = r["cid"]
        return out

    def why_node_source_provenance(self) -> dict:
        """{why_node_id: source_url}——已冊封根因中，evidence_url 命中現有收進來源者
        （spec 032 源→根因由來，讀端衍生、零新欄）。來源被刪→其 url 不在來源清單→自動不列（優雅）。"""
        source_urls = {g["url"] for g in self.list_source_groups()}
        out: dict = {}
        for w in self.list_why_nodes("anointed"):
            for u in (w.evidence_urls or []):
                if u in source_urls:
                    out[w.id] = u
                    break
        return out

    def set_seed_class(self, entry_id: int, cls: str) -> bool:
        """重分類種子（限種子容器）。cls∈{explainer,ordinary}；否則/非種子 → 回 False。"""
        if cls not in ("explainer", "ordinary"):
            return False
        sid = self._seeds_digest_id()
        if sid is None:
            return False
        cur = self.conn.execute(
            f"UPDATE digest_entries SET source_class=%s WHERE {self._OWN} AND id=%s AND digest_id=%s",
            (cls, entry_id, sid))
        self.conn.commit()
        return cur.rowcount > 0

    def get_entry_embedding(self, entry_id: int, tag: str) -> Vector | None:
        row = self.conn.execute(
            "SELECT vector_json FROM entry_embeddings WHERE entry_id=%s AND tag=%s",
            (entry_id, tag),
        ).fetchone()
        return json.loads(row["vector_json"]) if row else None

    def save_entry_embedding(self, entry_id: int, tag: str, vec: Vector) -> None:
        self.conn.execute(
            "INSERT INTO entry_embeddings (entry_id, tag, dim, vector_json)"
            " VALUES (%s,%s,%s,%s)"
            " ON CONFLICT (entry_id, tag) DO UPDATE SET dim=excluded.dim,"
            " vector_json=excluded.vector_json",
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
