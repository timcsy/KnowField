# 實作計畫：全部 PG——資料層 SQLite→Postgres

**Spec**: [spec.md](./spec.md) · **憲章 III（spec-driven）＋ I（TDD）**

## 相依必要性（憲章額外限制：新增第三方相依 MUST 說明必要性）
- **新增 `psycopg[binary]`（PG driver）＋ `testcontainers[postgres]`（測試用）**。
- **必要性**：vision 階段 31 定案「全部 PG」為部署 substrate（K8s 既有 cluster、往分享/多人走）。PG 是網路 DB，
  解掉 SQLite-on-K8s 的單寫者/PVC/Recreate 限制、且 mirrord read-only 可用 read-only role 結構保證。
  無 PG driver 無法連 PG，故此相依為**達成本階段目標所必需**。放鬆的是 spec 級慣例「核心含 repository 零相依」，
  非憲章條文（見 `history/084`）；核心演算法（chunk/ingest/distill/rag）仍純、不引入此相依。

## dialect 對應（SQLite → PG）
| SQLite | PG |
|---|---|
| `sqlite3.connect(path)` | `psycopg.connect(dsn, row_factory=dict_row)` |
| `?` 佔位 | `%s` |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `cur.lastrowid` | `INSERT ... RETURNING id` → `fetchone()["id"]` |
| `INSERT OR IGNORE` | `INSERT ... ON CONFLICT (key) DO NOTHING` |
| `INSERT OR REPLACE` | `INSERT ... ON CONFLICT (key) DO UPDATE SET ...` |
| `executescript(sql)` | 拆語句逐一 execute |
| `row_factory=sqlite3.Row` | `psycopg.rows.dict_row`（`r["c"]`／`r.keys()`／`dict(r)` 皆相容） |
| `PRAGMA table_info` / `ALTER`（_migrate 舊檔補欄） | **丟棄**（PG 從零起、SCHEMA 已完整；無舊 PG 檔） |

**parity 原則**：日期欄維持 `TEXT`（碼存/讀 ISO 字串，不改 TIMESTAMP）、布林維持 `INTEGER`（碼 `int()`/`bool()`）
——不「升級」型別，避免行為漂移。

## 連線
- `Repository.__init__(dsn=None)`：dsn 為 PG DSN（`postgresql://...`）；None→讀 env `KNOWFIELD_DATABASE_URL`。
- `Config`：加 `database_url`（env `KNOWFIELD_DATABASE_URL`）。app.py 改吃 DSN。

## 測試策略（守零安裝核心 TDD）
- **核心測試不碰 DB**：維持原樣、零安裝。
- **整合測試**：`conftest.py` 起 **session 級 testcontainer PG**；`temp_db()`／`web_helpers.temp_db()` 改成
  「在該 PG 上建一個乾淨資料庫、回其 DSN」＝per-test 隔離（等價原 `:memory:`／temp file）。
- **`Repository(":memory:")` 19 處** → sed 成 `Repository(temp_db())`＋補 import。
- **`test_epistemic_kind.py`** 直接用 `sqlite3` 測 _migrate 補欄——PG 下 _migrate 丟棄、改用 Repository/PG 驗 kind 欄存在。

## 步驟（TDD、逐段驗）
1. schema.py → PG DDL＋idempotent seed（ON CONFLICT）；init_db 拆語句。
2. repository.py → psycopg（連線、%s、RETURNING、ON CONFLICT）。
3. config.py＋app.py → DSN。
4. conftest.py＋temp_db()／web_helpers → PG；sed :memory:。
5. 先跑 test_store.py 綠（證 port 對）→ 再擴全套 344 綠。
6. 逐一修 parity bug（日期字串比較、IN (%s) 展開、dedup 指紋、autocommit/交易）。

## 驗收
repository 全走 PG、schema 在 PG 建立、既有 344 測在「核心 DB-less＋DB 層 PG」全綠、行為零回歸、
純核心測試維持零安裝、唯讀角色寫入被拒。範圍外（pgvector/多租戶/auth/領域分類/雙後端）未引入。
