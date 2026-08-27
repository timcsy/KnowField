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
    ingested_at TEXT DEFAULT '',
    owner_id INTEGER DEFAULT 1,       -- spec 063：每一列有主人
    persona_id INTEGER               -- spec 067：NULL ＝ 共用（預設共用，隔離是選擇）
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

CREATE TABLE IF NOT EXISTS personas (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER DEFAULT 1,
    name TEXT NOT NULL,
    color TEXT DEFAULT '',
    created_at TEXT
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
    conversation_id INTEGER,
    origin TEXT DEFAULT '',
    last_rehearsed_at TEXT DEFAULT '',   -- spec 068：上次被推到你眼前是什麼時候
    owner_id INTEGER DEFAULT 1,       -- spec 063：每一列有主人
    persona_id INTEGER               -- spec 067：NULL ＝ 共用（預設共用，隔離是選擇）
);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    title TEXT,
    messages TEXT DEFAULT '[]',
    why_node_id INTEGER,
    created_at TEXT,
    temporary INTEGER DEFAULT 0,
    last_activity_at TEXT,
    chapters TEXT DEFAULT '[]',
    carried_kind TEXT DEFAULT '',
    carried_ref TEXT DEFAULT '',
    owner_id INTEGER DEFAULT 1,       -- spec 063：每一列有主人
    persona_id INTEGER               -- spec 067：NULL ＝ 共用（預設共用，隔離是選擇）
);

CREATE TABLE IF NOT EXISTS article_roots (
    article_id INTEGER NOT NULL,
    why_node_id INTEGER NOT NULL,
    layer TEXT DEFAULT 'body'
);

CREATE TABLE IF NOT EXISTS domains (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id INTEGER,
    created_at TEXT DEFAULT '',
    owner_id INTEGER DEFAULT 1,       -- spec 063：每一列有主人
    persona_id INTEGER               -- spec 067：NULL ＝ 共用（預設共用，隔離是選擇）
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
    created_at TEXT DEFAULT '',
    owner_id INTEGER DEFAULT 1,       -- spec 063：每一列有主人
    persona_id INTEGER               -- spec 067：NULL ＝ 共用（預設共用，隔離是選擇）
);

-- spec 072（階段 68）：**別人的** knowie base——場自己去 GitHub 拿回來的。
-- ⚠️ 跟自己的知識**分開放**：它是外來的、不可信的文字（下一刀會餵給 LLM 消化）。
--    混在同一張表裡，之後就分不清哪一條是你自己的場。
CREATE TABLE IF NOT EXISTS ext_bases (
    id SERIAL PRIMARY KEY,
    repo TEXT NOT NULL,                  -- owner/name
    name TEXT DEFAULT '',                -- 顯示名（預設取 repo 尾段）
    branch TEXT DEFAULT '',              -- 抓的時候用的 default_branch（**不寫死 main**）
    private INTEGER DEFAULT 0,
    installation_id TEXT DEFAULT '',
    fetched_at TEXT DEFAULT '',          -- ⚠️ 樹一抓下來就開始過期，用到它的輸出要顯示這個
    tree_truncated INTEGER DEFAULT 0,    -- ⚠️ GitHub 截斷了要說，不能靜默給不完整的樹
    n_paths INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',       -- pending｜fetching｜indexing｜ok｜error
    error TEXT DEFAULT '',
    created_at TEXT,
    owner_id INTEGER DEFAULT 1,
    persona_id INTEGER
);

-- `knowledge/**` 的內容（六層全收）。layer 由路徑導出：experience｜concepts｜principles
-- ｜vision｜history｜episodes｜other
CREATE TABLE IF NOT EXISTS ext_items (
    id SERIAL PRIMARY KEY,
    base_id INTEGER NOT NULL,
    layer TEXT DEFAULT '',
    path TEXT NOT NULL,
    body TEXT DEFAULT '',
    owner_id INTEGER DEFAULT 1,
    persona_id INTEGER
);

-- spec 073：從 `ext_items` 抽出來的判準句 ＋ 它的向量。
-- ⚠️ 獨立一張表而不是塞進 `entry_embeddings`：那張的 id 空間已經被
--    digest_entries（正）與 why_nodes（負）佔了，再擠進去就是等著碰撞。
--    而這裡的向量**跟著那個 base 的重抓一起作廢**，語意剛好對得上。
CREATE TABLE IF NOT EXISTS ext_lessons (
    id SERIAL PRIMARY KEY,
    base_id INTEGER NOT NULL,
    layer TEXT DEFAULT '',
    text TEXT NOT NULL,
    tag TEXT DEFAULT '',
    vector_json TEXT DEFAULT '',
    owner_id INTEGER DEFAULT 1,
    persona_id INTEGER
);

-- spec 076：`ext_items` 切出來的塊 ＋ 向量。
-- ⚠️ 為什麼要切：`ext_items` 共 184 萬字、最大一份 226,460 字——**整份塞不進 context**。
--    而切了才有「引用看得出是哪一份檔案的哪一段」。
-- ⚠️ spec 080 起**沒有任何程式寫這張表**（「專案是第二個場」已退役）。
-- 留著只為了讓 `delete_ext_base` 清得掉正式庫裡的舊列——別再拿它當語料。
CREATE TABLE IF NOT EXISTS ext_chunks (
    id SERIAL PRIMARY KEY,
    base_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    layer TEXT DEFAULT '',
    path TEXT NOT NULL,
    seq INTEGER DEFAULT 0,
    text TEXT NOT NULL,
    tag TEXT DEFAULT '',
    vector_json TEXT DEFAULT '',
    owner_id INTEGER DEFAULT 1,
    persona_id INTEGER
);

-- ⚠️ 第三種東西：**查證用的事實**，不給人讀、不進收件匣、不當判準。
--    只回答一件事：「這個路徑還在嗎」。所以只存路徑，**沒有 body 欄**。
CREATE TABLE IF NOT EXISTS ext_paths (
    id SERIAL PRIMARY KEY,
    base_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    owner_id INTEGER DEFAULT 1,
    persona_id INTEGER
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


# spec 044：**對既有表**要補的欄。新庫由 SCHEMA 直接帶出，這張清單只服務**已存在**的庫
# ——`CREATE TABLE IF NOT EXISTS` 對既有表是 no-op，所以少了這一步，正式庫永遠不會長出新欄。
#
# ⚠️ 這是宣告式清單，不是 migration 框架：**不支援改型別或刪欄**。
# 單人專案、一張清單就夠（憲章 IV）；真的需要時再升級，不預先蓋。
_ADD_COLUMNS: list[tuple[str, str, str]] = [
    # spec 080：這個專案落成來源之後歸在哪個領域。
    # ⚠️ **記住它，別靠名字回頭猜**——repo 改名或領域改名就對不上，而且不報錯。
    ("ext_bases", "domain_id", "INTEGER"),
    ("conversations", "carried_kind", "TEXT DEFAULT ''"),   # ''｜article｜source
    ("conversations", "carried_ref", "TEXT DEFAULT ''"),    # 文章 id 或來源 url
    ("conversations", "domain_id", "INTEGER"),              # spec 048：歸屬的領域（NULL＝未歸屬）
    ("articles", "conversation_id", "INTEGER"),             # spec 049：從哪段對話生的
    ("articles", "domain_id", "INTEGER"),                   # spec 049：歸屬的領域
    ("why_nodes", "domain_id", "INTEGER"),                  # spec 049：歸屬的領域
    # spec 050：來源也歸屬。⚠️ 一個「來源」＝一個 url ＝**多個塊**，所以整組塊一起設。
    ("digest_entries", "domain_id", "INTEGER"),
    # spec 055：**封存＝離開活的場，留下遺骸**（超新星／黑洞／細胞凋亡：結束不等於湮滅）。
    # 它是**一個通用動作**——領域與四種知識都適用。
    # ⚠️ `archived_root`＝是被哪個領域的封存**連帶**帶走的（NULL＝自己被封的）。
    #    復原時靠它把「同一批」找回來——沒有它，復原就只能靠時間戳猜。
    ("domains", "archived_at", "TEXT DEFAULT ''"),
    ("domains", "archived_from", "INTEGER"),   # 封存當下的父領域（給復原用）
    ("domains", "archived_root", "INTEGER"),
    ("why_nodes", "archived_at", "TEXT DEFAULT ''"),
    ("why_nodes", "archived_root", "INTEGER"),
    ("articles", "archived_at", "TEXT DEFAULT ''"),
    ("articles", "archived_root", "INTEGER"),
    ("conversations", "archived_at", "TEXT DEFAULT ''"),
    ("conversations", "archived_root", "INTEGER"),
    ("digest_entries", "archived_at", "TEXT DEFAULT ''"),
    ("digest_entries", "archived_root", "INTEGER"),
    # spec 056：**第二次的死**——抹除。內容全空，`erased_at` 記時間，**列還在**。
    # ⚠️ 連「這裡曾經有東西」都不見的話，那不是死亡，是從沒存在過。
    ("domains", "erased_at", "TEXT DEFAULT ''"),
    ("why_nodes", "erased_at", "TEXT DEFAULT ''"),
    ("articles", "erased_at", "TEXT DEFAULT ''"),
    ("conversations", "erased_at", "TEXT DEFAULT ''"),
    ("digest_entries", "erased_at", "TEXT DEFAULT ''"),
    # spec 062：這條理解是誰寫的。''＝AI 蒸餾的候選（既有）｜'self'＝人自己寫且有出處
    # ｜'self:judgment'＝人自己寫、明確宣告**無外部依據**。
    # ⚠️ 第三種要**存**不要推導：「欄位都空著」和「明確宣告沒有依據」在資料上長得一樣，
    #    而後者是一個**判斷**——資訊存在的時候不要把它丟掉。
    ("why_nodes", "origin", "TEXT DEFAULT ''"),
    # ⚠️ spec 080 起**沒有人寫這一欄**：「站在專案裡」不再是第二個場，
    #    專案就是來源，站在哪由 `domain_id` 說。留欄只為了不動正式庫的舊列。
    ("conversations", "ext_base_id", "INTEGER"),
    # spec 063（階段 58）：B-底層——每一列有主人。
    # ⚠️ 預設 1 ＝ 既有的單一使用者 ⇒ 補欄本身就是 backfill，不需要另一支腳本。
    ("domains", "owner_id", "INTEGER DEFAULT 1"),
    ("why_nodes", "owner_id", "INTEGER DEFAULT 1"),
    ("articles", "owner_id", "INTEGER DEFAULT 1"),
    ("conversations", "owner_id", "INTEGER DEFAULT 1"),
    ("digest_entries", "owner_id", "INTEGER DEFAULT 1"),
    # spec 067：persona ＝ **隱私的硬隔離**。⚠️ NULL ＝ 共用
    # ——既有資料全部留在共用層（不加預設值就是這個效果，正是要的）。
    ("domains", "persona_id", "INTEGER"),
    ("why_nodes", "persona_id", "INTEGER"),
    ("articles", "persona_id", "INTEGER"),
    ("conversations", "persona_id", "INTEGER"),
    ("digest_entries", "persona_id", "INTEGER"),
    # spec 068：上次被推到你眼前是什麼時候。⚠️ 挑選只靠**時間**——
    # 任何「熱門度」進到這裡就是馬太陷阱：被引用最多的一直被推出來，
    # 而你最需要重新遇到的正好是**你快忘了的那些**。
    ("why_nodes", "last_rehearsed_at", "TEXT DEFAULT ''"),
    # spec 069：這個地址是**算出來的**還是**人放的**。
    # ⚠️ 分不出來的話，你會把機器的猜測當成自己的判斷——而那正是
    # 「猜出來的歸屬會看起來跟真的一樣」在講的事。
    ("why_nodes", "assigned_by", "TEXT DEFAULT ''"),
    ("conversations", "assigned_by", "TEXT DEFAULT ''"),
    ("articles", "assigned_by", "TEXT DEFAULT ''"),
    ("digest_entries", "assigned_by", "TEXT DEFAULT ''"),
]


def _existing_columns(conn, table: str) -> set[str]:
    """回這張表現有的欄名。⚠️ 表不存在時**讓錯誤丟出來**，不要吞。"""
    if getattr(conn, "dialect", "postgres") == "sqlite":
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        names = {r["name"] for r in rows}
        if not names:
            raise ValueError(f"表不存在或沒有任何欄：{table}")
        return names
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
        (table,)).fetchall()
    names = {r["column_name"] for r in rows}
    if not names:
        raise ValueError(f"表不存在或沒有任何欄：{table}")
    return names


def _ensure_columns(conn, specs=None) -> list[str]:
    """冪等補欄：**先問有哪些欄、缺的才加**。回實際加了哪幾個（供 log）。

    ⚠️ 為什麼不是 `ALTER TABLE … ADD COLUMN` 包 try/except：
    那會把「欄已存在」跟「型別寫錯／表不存在／權限不足」混成同一件事
    ——真的錯了也靜默過去。本專案這兩天連續撞到的正是這類沉默失敗
    （`history/102` 的 import 路徑錯、`history/104` 的 typeset 被吞）。
    ⚠️ 也不是 `ADD COLUMN IF NOT EXISTS`：PG 有、**SQLite 沒有**，會破雙後端 parity（spec 036）。
    """
    added = []
    for table, col, decl in (specs if specs is not None else _ADD_COLUMNS):
        if col in _existing_columns(conn, table):
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        added.append(f"{table}.{col}")
    if added:
        conn.commit()
    return added


def init_db(conn) -> None:
    """建 schema（冪等，CREATE IF NOT EXISTS）＋確保單一使用者興趣畫像列存在。依 conn.dialect 分岔自增型別。

    spec 044 起**含補欄**（`_ensure_columns`）：既有表不會因為 SCHEMA 改了就長出新欄
    （`CREATE TABLE IF NOT EXISTS` 對既有表是 no-op），所以新欄要另外補。
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
    added = _ensure_columns(conn)
    if added:
        # 只會發生一次的事，事後查得到很重要（憲章 V）
        import logging
        logging.getLogger("knowfield.store").info("補欄：%s", ", ".join(added))
