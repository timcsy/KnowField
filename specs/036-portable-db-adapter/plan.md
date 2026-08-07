# 實作計畫：可攜資料層 adapter（SQLite ↔ PG）

**Spec**: [spec.md](./spec.md) · **憲章 I（TDD）＋ III（spec-driven）＋ IV（薄、零新相依）**

## 相依（憲章額外限制）
- **零新相依**：SQLite 走 stdlib `sqlite3`；psycopg 已在（階段 31）。**不引入 SQLAlchemy／pgvector**。

## 設計：薄 dialect adapter
- **新 `store/db.py`**：
  - `connect(url) -> _Conn`：url 以 `postgres://`/`postgresql://` 開頭→psycopg（dict_row）；否則→sqlite3（`Row`、去 `sqlite://` 前綴、支援 `:memory:`/檔案路徑）。
  - `_Conn`：薄包裝，`execute(sql, params)`——**sqlite 時把 `%s`→`?`**（資料層一律寫 `%s`）；`commit()`/`close()` 直通；
    `.dialect ∈ {sqlite, postgres}`。回傳 cursor，row 皆支援 `r["c"]`／`r.keys()`／`dict(r)`（psycopg dict_row 與 sqlite3.Row 皆相容）。
- **schema.py**：`init_db(conn)` 依 `conn.dialect` 產生自增型別——PG `SERIAL PRIMARY KEY`、SQLite 換 `INTEGER PRIMARY KEY`。
  其餘 DDL 兩後端通用（`RETURNING`/`ON CONFLICT`/`excluded.` SQLite 3.49.1 皆支援）。
- **repository.py**：`__init__` 改 `self.conn = db.connect(dsn)`（取代直接 psycopg.connect）。**SQL 本體不動**（已全用 `%s`＋RETURNING＋ON CONFLICT）。
- **config.py**：`database_url` 未設時**預設本地 SQLite 檔**（零 server 本地預設）；prod 明設 PG DSN。
- **測試 harness**：`temp_db()`（rag_helpers/web_helpers）依 `KNOWFIELD_TEST_BACKEND`（預設 `sqlite`）：
  - `sqlite`→新臨時 `.db` 檔（零 server、零 Docker）；`postgres`→`tests/pgtest.fresh_pg_dsn()`（testcontainers，per-test 新 DB）。

## 佔位符翻譯的安全性
- 資料層 SQL **無字面 `%`**（無 LIKE '%…%'、無 strftime）→ `%s`→`?` 直接 replace 安全。psycopg 端維持 `%s`。

## 步驟（TDD、兩後端驗）
1. `store/db.py` adapter。
2. schema.py 依 dialect 分岔自增型別。
3. repository.py 走 db.connect。
4. config 預設本地 SQLite。
5. temp_db 依 env 選後端（預設 sqlite）。
6. **本地 `pytest`（SQLite，零 server）全綠** → **`KNOWFIELD_TEST_BACKEND=postgres pytest`（PG）全綠** ＝parity。
7. 逐一修兩後端差異（若有：日期字串、rowcount、交易）。

## 驗收
本地零 server/零 Docker 全綠（SQLite）；PG 後端同套全綠；app 本地 SQLite/prod PG 皆起；既有 352 測零回歸；
零新相依、未引入 ORM/pgvector。動工完成→`history/084` 標「不騎牆」段 superseded、開新 history 記 re-route。
