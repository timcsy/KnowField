# Feature Specification: 本地 SQLite ＋ prod PG——可攜資料層 adapter

**Feature Branch**: `036-portable-db-adapter`

**Created**: 2026-08-07

**Status**: Draft

**Input**: 見 vision 階段 33、`draft/2026-08-07-本地SQLite與prod-PG雙後端`、`history/084`（re-route）。

## User Scenarios & Testing *(mandatory)*

> re-route（承階段 31）：使用者要**本地零 server**（不想跑 Docker、也不想跑原生 PG server）。SQLite 是唯一
> 零-server 的 SQL 庫。本功能＝加一層薄 dialect adapter，讓**同一份資料層碼**跑 SQLite（本地）或 PG（prod）。

### User Story 1 - 本地零 server 跑起來（Priority: P1）

擁有者在本機開發時，**不需要啟動任何資料庫 server（不用 Docker、不用 PG）**，app 與測試直接用 SQLite 檔案跑。

**Why this priority**: 這是整個 re-route 的存在理由（使用者的真痛）。

**Independent Test**: 在沒有任何 DB server、沒有 Docker 的環境，`pytest` 全綠、app 起得來。

**Acceptance Scenarios**:

1. **Given** 沒有 DB server 也沒有 Docker，**When** 跑完整測試套件，**Then** 全數通過（走 SQLite）。
2. **Given** 未設任何 DB 連線，**When** 本地啟動 app，**Then** 以本地 SQLite 檔運作。

---

### User Story 2 - prod 仍是 PG、且行為與本地一致（Priority: P1）

正式環境用 Postgres（承階段 31 的部署 substrate）；**本地 SQLite 與 prod PG 的行為必須一致**，本地測綠代表 prod 也會綠。

**Why this priority**: 雙後端最大的風險是 drift（本地綠、prod 不一定）。若不保證一致，這功能弊大於利。

**Independent Test**: **同一套測試在 SQLite 與 PG 兩個後端都能跑、都全綠**。

**Acceptance Scenarios**:

1. **Given** 選擇 Postgres 後端，**When** 跑同一套測試，**Then** 全數通過（與 SQLite 結果一致）。
2. **Given** 任一資料操作，**When** 在兩後端分別執行，**Then** 可觀察結果一致（id 回傳、去重/覆寫、排序、日期）。

---

### Edge Cases

- **佔位符差異**：兩後端佔位符寫法不同——adapter MUST 讓資料層碼只寫一種、對另一後端自動翻譯。
- **自增主鍵**：兩後端語法不同——schema MUST 依後端產生對應寫法。
- **連線來源辨識**：adapter MUST 從連線字串判斷該用哪個後端（檔案/記憶體→SQLite、網路 DSN→PG）。
- **測試隔離**：每個整合測試 MUST 拿到乾淨、彼此隔離的資料庫（SQLite＝新臨時檔；PG＝新資料庫）。
- **pgvector（已知邊界）**：向量索引是 PG-only；本功能**不含** pgvector；未來檢索升級時該功能 PG 專屬、SQLite 走純 Python 降級。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 資料層 MUST 能以 **SQLite（本地、零 server）** 或 **Postgres（prod）** 運作，由連線字串決定。
- **FR-002**: 資料層程式碼 MUST 只寫一種 SQL 方言，adapter 負責對另一後端翻譯（佔位符、自增型別）。
- **FR-003**: 兩後端 MUST 行為一致（parity）——所有既有功能與資料操作的可觀察結果相同。
- **FR-004**: 完整測試套件 MUST 能在 **SQLite 與 Postgres 兩後端**分別執行、皆全綠。
- **FR-005**: 本地預設 MUST 為零 server（SQLite）——不需 Docker、不需 DB server 即可跑測試與 app。
- **FR-006**: 整合測試 MUST 各自取得乾淨、彼此隔離的資料庫狀態（兩後端皆然）。
- **FR-007**: 核心 DB-less 測試 MUST 維持零安裝、不受影響。
- **FR-008**: MUST NOT 引入完整 ORM 或 pgvector；SQLite 支援 MUST 用標準函式庫（零新相依）。
- **FR-009**: 既有 352 測 MUST 不回歸。

### Key Entities *(include if feature involves data)*

> 不改變任何實體語義，只在儲存層下加一層後端抽象。實體同階段 31（why_node/digest/conversation/source/article…）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 在**無 DB server、無 Docker** 的環境，完整測試套件 **100%** 通過（SQLite）。
- **SC-002**: 選 Postgres 後端時，**同一套**測試 **100%** 通過（與 SQLite 一致）。
- **SC-003**: 本地啟動 app **零 server**（SQLite 檔）；prod 啟動用 PG——皆可運作。
- **SC-004**: 既有 352 測 **0** 回歸。
- **SC-005**: **0** 新增第三方相依用於 SQLite 支援（用標準函式庫）；**未**引入 ORM／pgvector。

## Assumptions

- **SQLite 版本足夠**：已實測 SQLite 3.49.1 支援 `RETURNING`（3.35+）、`ON CONFLICT`（3.24+）、Row 存取——SQL 幾乎可攜。
- **薄 adapter，非 SQLAlchemy**：現況 SQL 已近可攜，只需抽象「連線＋佔位符＋dict row＋自增型別」，不必上完整 ORM。
- **drift 靠測試消除**：本地 SQLite＋CI/prod PG，**同套測試兩後端跑**——drift 被機械抓出，非靠祈禱。
- **re-route 有記**：本功能 supersede 階段 31「不騎牆」立場；動工完成時 `history/084` 標該段 superseded、開新 history。
- **範圍嚴限**：只做 sqlite/psycopg 雙後端 parity；ORM、pgvector、行為改變皆 out。
