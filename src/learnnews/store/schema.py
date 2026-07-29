"""SQLite schema（對應 data-model.md）。"""

from __future__ import annotations

import sqlite3

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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    truncated_count INTEGER DEFAULT 0,
    missing_sources TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS digest_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    digest_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    matched_topic TEXT DEFAULT '',
    article_body TEXT DEFAULT '',
    article_headline TEXT DEFAULT '',
    figure_url TEXT DEFAULT '',
    figure_kind TEXT DEFAULT '',
    source_class TEXT DEFAULT 'ordinary',  -- 'ordinary' | 'explainer'（種子 spec 006）
    source_id TEXT DEFAULT ''              -- 條目來源 id（spec 017 分區用；join sources.type）
);

CREATE TABLE IF NOT EXISTS entry_embeddings (
    entry_id INTEGER NOT NULL,      -- → digest_entries.id
    tag TEXT NOT NULL,              -- embedder 身分：'hashing-256' / 'openai-<model>'
    dim INTEGER NOT NULL,
    vector_json TEXT NOT NULL,
    PRIMARY KEY (entry_id, tag)
);

CREATE TABLE IF NOT EXISTS behavior_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    at TEXT
);

CREATE TABLE IF NOT EXISTS why_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim TEXT NOT NULL,               -- 根因主張（一段話）
    evidence_urls TEXT DEFAULT '[]',   -- JSON：證據原文連結（來源種子 url）
    touchstones TEXT DEFAULT '[]',     -- JSON：試金石逐條 [{name, passed}]
    ladder TEXT DEFAULT '[]',          -- JSON：why 階梯（表面→bedrock，每層一句）
    fog_flag INTEGER DEFAULT 0,        -- 是否有霧詞（假根因旗標）
    status TEXT DEFAULT 'candidate',   -- 'candidate'（候選）| 'anointed'（人冊封的吸引子）
    source_entry_id INTEGER,           -- 來源種子 digest_entries.id
    created_at TEXT,                   -- 建立時間（呼叫端傳入）
    conversation_id INTEGER            -- spec 025：由來對話（多條根因可共用一份；取代 conversations.why_node_id 為事實來源）
);

-- 對話的「由來」存檔（spec 023，episodes 層）：第一個落庫的對話產物。唯讀參考、不入地基（原則 6）。
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,                        -- 自動「由來」標題（一句摘要）
    messages TEXT DEFAULT '[]',        -- JSON：整段訊息（role/content/sources）
    why_node_id INTEGER,               -- 可空：連到的核心理解；無 FK（刪根因→對話變獨立、不崩）
    created_at TEXT
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # 確保單一使用者的興趣畫像列存在
    conn.execute(
        "INSERT OR IGNORE INTO interest_profile (id, explicit_topics, learned_weights)"
        " VALUES (1, '[]', '{}')"
    )
    _migrate(conn)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """對既有 DB 補欄（CREATE TABLE IF NOT EXISTS 不會改既有表）。冪等。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(digest_entries)").fetchall()}
    if "source_class" not in cols:   # spec 006：既有增量 1 的 db 補上種子分類欄
        conn.execute(
            "ALTER TABLE digest_entries ADD COLUMN source_class TEXT DEFAULT 'ordinary'")
    if "source_id" not in cols:      # spec 017：分區用（條目來源 id）
        conn.execute("ALTER TABLE digest_entries ADD COLUMN source_id TEXT DEFAULT ''")
    # spec 012：既有 db 補 why_nodes 表（CREATE IF NOT EXISTS，不動既有表）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS why_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim TEXT NOT NULL,
            evidence_urls TEXT DEFAULT '[]',
            touchstones TEXT DEFAULT '[]',
            fog_flag INTEGER DEFAULT 0,
            status TEXT DEFAULT 'candidate',
            ladder TEXT DEFAULT '[]',
            source_entry_id INTEGER,
            created_at TEXT
        )""")
    # spec 012 品質補強：既有 why_nodes 補 ladder 欄（why 階梯）
    wn_cols = {r[1] for r in conn.execute("PRAGMA table_info(why_nodes)").fetchall()}
    if wn_cols and "ladder" not in wn_cols:
        conn.execute("ALTER TABLE why_nodes ADD COLUMN ladder TEXT DEFAULT '[]'")
    # spec 025：why_nodes 補 conversation_id 欄（由來連結改存 why_node 側，多條可共用一份）
    if wn_cols and "conversation_id" not in wn_cols:
        conn.execute("ALTER TABLE why_nodes ADD COLUMN conversation_id INTEGER")
        # 一次性回填：既有 conversations.why_node_id → why_nodes.conversation_id（既有「← 由來」不斷）
        has_conv = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
        ).fetchone()
        if has_conv:
            conn.execute(
                "UPDATE why_nodes SET conversation_id="
                "(SELECT c.id FROM conversations c WHERE c.why_node_id=why_nodes.id"
                " ORDER BY c.id ASC LIMIT 1)"
                " WHERE conversation_id IS NULL")
    # spec 023：既有 db 補 conversations 表（對話由來存檔，CREATE IF NOT EXISTS，不動既有表）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            messages TEXT DEFAULT '[]',
            why_node_id INTEGER,
            created_at TEXT
        )""")
