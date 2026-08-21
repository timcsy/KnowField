"""可攜 schema（對應 data-model.md）。spec 036：一份 DDL 跑 SQLite 或 Postgres。

parity 原則：日期欄維持 TEXT（碼存/讀 ISO 字串）、布林維持 INTEGER（碼 int()/bool()）——不「升級」型別。
自增主鍵在 PG＝`SERIAL PRIMARY KEY`、SQLite＝`INTEGER PRIMARY KEY`（依 conn.dialect 分岔）。
"""

from __future__ import annotations

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    access_method TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_fetch_at TEXT,
    last_status TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,
    external_id TEXT,
    title TEXT NOT NULL,
    abstract TEXT DEFAULT '',
    url TEXT NOT NULL,
    published_at TEXT,
    lang TEXT DEFAULT 'en',
    cluster_id INTEGER,
    fetched_at TEXT,
    content_hash TEXT,
    UNIQUE(content_hash)
);

CREATE TABLE IF NOT EXISTS clusters (
    id SERIAL PRIMARY KEY,
    canonical_item_id INTEGER NOT NULL,
    signature TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS interest_profile (
    id INTEGER PRIMARY KEY,
    explicit_topics TEXT NOT NULL DEFAULT '[]',
    learned_weights TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS digests (
    id SERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    truncated_count INTEGER DEFAULT 0,
    missing_sources TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS digest_entries (
    id SERIAL PRIMARY KEY,
    digest_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    matched_topic TEXT DEFAULT '',
    article_body TEXT DEFAULT '',
    article_headline TEXT DEFAULT '',
    figure_url TEXT DEFAULT '',
    figure_kind TEXT DEFAULT '',
    source_class TEXT DEFAULT 'ordinary',
    source_id TEXT DEFAULT '',
    note TEXT DEFAULT '',
    ingested_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS entry_embeddings (
    entry_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector_json TEXT NOT NULL,
    PRIMARY KEY (entry_id, tag)
);

CREATE TABLE IF NOT EXISTS behavior_signals (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    at TEXT
);

CREATE TABLE IF NOT EXISTS why_nodes (
    id SERIAL PRIMARY KEY,
    claim TEXT NOT NULL,
    evidence_urls TEXT DEFAULT '[]',
    touchstones TEXT DEFAULT '[]',
    ladder TEXT DEFAULT '[]',
    fog_flag INTEGER DEFAULT 0,
    kind TEXT DEFAULT '',
    src_from INTEGER DEFAULT 0,
    src_to INTEGER DEFAULT 0,
    source_quote TEXT DEFAULT '',
    source_page INTEGER DEFAULT 0,
    status TEXT DEFAULT 'candidate',
    source_entry_id INTEGER,
    created_at TEXT,
    conversation_id INTEGER
);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    title TEXT,
    messages TEXT DEFAULT '[]',
    why_node_id INTEGER,
    created_at TEXT,
    temporary INTEGER DEFAULT 0,
    last_activity_at TEXT,
    chapters TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS translation_units (
    unit_key TEXT PRIMARY KEY,
    markdown TEXT NOT NULL,
    last_used_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    topic TEXT DEFAULT '',
    title TEXT DEFAULT '',
    markdown TEXT NOT NULL,
    length TEXT DEFAULT '',
    level TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
"""


def _statements(script: str) -> list[str]:
    """把多語句 DDL 拆成逐句（去掉 -- 行註解、空句）。psycopg 一次 execute 一句。"""
    lines = [ln for ln in script.splitlines() if not ln.strip().startswith("--")]
    out = []
    for stmt in "\n".join(lines).split(";"):
        if stmt.strip():
            out.append(stmt)
    return out


def init_db(conn) -> None:
    """建 schema（冪等，CREATE IF NOT EXISTS）＋確保單一使用者興趣畫像列存在。依 conn.dialect 分岔自增型別。

    註：不含舊 SQLite 檔的 _migrate 補欄（新庫從零起、SCHEMA 已含所有欄）。
    """
    schema = SCHEMA
    if getattr(conn, "dialect", "postgres") == "sqlite":
        schema = schema.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY")
    for stmt in _statements(schema):
        conn.execute(stmt)
    conn.execute(
        "INSERT INTO interest_profile (id, explicit_topics, learned_weights)"
        " VALUES (1, '[]', '{}') ON CONFLICT (id) DO NOTHING"
    )
    conn.commit()
