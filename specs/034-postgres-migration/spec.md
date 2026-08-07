# Feature Specification: 全部 PG——資料層從 SQLite 遷到 Postgres

**Feature Branch**: `034-postgres-migration`

**Created**: 2026-08-07

**Status**: Draft

**Input**: User description: 見 vision 階段 31、`history/084`、`draft/2026-07-23-部署與介面路線` ⑤。

## User Scenarios & Testing *(mandatory)*

> 本功能是**資料層 substrate 換血（parity migration）**，不是使用者可見的新行為。這裡的「使用者」是
> **維運/開發者**與**其知識不可被損毀的擁有者**。所有 story 圍繞「換了地基、行為一模一樣、且能被驗證」。

### User Story 1 - 換 substrate 但行為零改變（Priority: P1）

擁有者把 KnowField 的資料層從 SQLite 換成 Postgres 後，**所有既有功能表現與換之前完全一致**——收進、聊天、
整理成核心理解、生成文章、來源展示都照舊，沒有任何行為差異或資料遺失。

**Why this priority**: 這是整個遷移的存在理由。substrate 是為了部署（K8s、往多人走），但**換地基不能動到上層行為**
——否則就不是遷移、是改產品。零回歸是唯一及格線。

**Independent Test**: 既有的完整測試套件（344 測）在 Postgres 後端下全數通過、行為與 SQLite 版一致，即證明 parity。

**Acceptance Scenarios**:

1. **Given** 既有 344 測在 SQLite 下全綠，**When** 資料層改用 Postgres 跑同一套測試，**Then** 全數仍通過、無行為差異。
2. **Given** 一個空的 Postgres，**When** 應用啟動，**Then** schema（所有表與索引）自動建立成功。
3. **Given** Repository 的每個資料操作（save/list/get/delete：why_nodes、digests、conversations、articles、sources 等），
   **When** 在 Postgres 上執行，**Then** 回傳結果與 SQLite 版語義一致（含 id 回傳、去重/覆寫、排序、日期）。

---

### User Story 2 - 核心測試維持零安裝、離線、秒跑（Priority: P1）

開發者跑純演算法測試（分塊、蒸餾、檢索、排序等不碰資料庫的邏輯）時，**不需要安裝或啟動任何資料庫**，
測試照舊離線、秒級完成。

**Why this priority**: 這是專案核心工程價值（experience「把重量級相依藏在窄介面後、預設離線，TDD 才能零安裝」）。
若遷移逼得**每個**測試都要 Postgres，就把最寶貴的快速 TDD 迴圈賠掉了。分層是不可退讓的約束。

**Independent Test**: 在**沒有**可用 Postgres／容器環境下，純核心測試仍能全部執行並通過；只有碰資料庫的整合測試會被跳過或標記需要 Postgres。

**Acceptance Scenarios**:

1. **Given** 沒有 Postgres 可用，**When** 只跑純核心測試，**Then** 全數通過、不因缺資料庫而失敗。
2. **Given** 有容器化 Postgres 可用，**When** 跑碰資料庫的整合測試，**Then** 每個測試拿到一個乾淨、彼此隔離的資料庫狀態。

---

### User Story 3 - 以 Postgres 連線資訊啟動、且開發可安全讀遠端（Priority: P2）

維運者用環境變數提供的 Postgres 連線資訊啟動應用；開發者可讓本地開發**唯讀**地連到遠端資料，
而**絕不可能寫壞**真實資料。

**Why this priority**: 這是遷移的部署收益（可上 K8s、可用 mirrord read-only 開發）。唯讀必須是**結構保證**
（資料庫層拒絕寫入），不是「我記得只讀」的自律——呼應原則 3「保證做進結構」。

**Independent Test**: 用 env 連線資訊啟動應用可正常運作；用唯讀角色連線時，任何寫入都被資料庫拒絕。

**Acceptance Scenarios**:

1. **Given** 環境變數提供 Postgres 連線資訊，**When** 應用啟動，**Then** 正常連上並運作。
2. **Given** 一個唯讀資料庫角色，**When** 嘗試寫入，**Then** 被資料庫拒絕（結構上不可能污染真實資料）。

---

### Edge Cases

- **`:memory:` 沒有 Postgres 對應**：19 處測試用 SQLite 記憶體庫求「快、隔離、免清理」。遷移後每個這類測試改拿
  一個**乾淨且獨立的 Postgres 資料庫/schema**，測完即棄——語義（隔離、無殘留）必須等價。
- **id 回傳**：SQLite 靠 `lastrowid`；Postgres 需 `RETURNING`。所有「插入後取新 id」的路徑都要覆蓋、驗證一致。
- **去重/覆寫語義**：SQLite `INSERT OR IGNORE/REPLACE` 換成 Postgres `ON CONFLICT`——衝突鍵與行為必須逐一對應，
  不可靜默改變（例：原本忽略的變成報錯，或原本覆寫的變成新增重複）。
- **日期/字串/布林**：SQLite 弱型別 vs Postgres 強型別——日期字串比較、布林、NULL 語義的差異不可造成行為漂移。
- **交易與併發**：Postgres 顯式交易/隔離級別下，既有「寫入後即讀」的假設仍成立。
- **遷移當下的真實資料**：擁有者現有的知識（現行資料）在切換過程中**先備份**，遺失風險為零。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系統的資料持久層 MUST 全面改用 Postgres；不保留 SQLite 後端、不做雙後端並存（使用者定案「全部 PG、不騎牆」）。
- **FR-002**: 遷移 MUST 維持**行為 parity**——所有既有功能與資料操作的可觀察結果，與 SQLite 版完全一致。
- **FR-003**: 既有完整測試套件（344 測）MUST 在 Postgres 後端下全數通過，且無行為回歸。
- **FR-004**: 資料 schema（所有表與索引）MUST 能在一個空 Postgres 上自動、冪等地建立。
- **FR-005**: 不碰資料庫的純核心測試 MUST 維持零安裝、離線、可執行；不得因遷移而被迫需要 Postgres。
- **FR-006**: 碰資料庫的整合測試 MUST 各自取得**乾淨、彼此隔離**的資料庫狀態（等價於原 `:memory:`／temp db 的隔離）。
- **FR-007**: 應用 MUST 能以**環境變數**提供的 Postgres 連線資訊啟動；連線密鑰 MUST NOT 進入版本庫。
- **FR-008**: 系統 MUST 支援以**唯讀資料庫角色**連線，使任何寫入在資料庫層被拒絕（供 mirrord read-only 開發用）。
- **FR-009**: 核心演算法模組（分塊/進料/蒸餾/檢索）MUST 維持不變、不被本遷移改動。
- **FR-010**: 遷移前 MUST 提供既有真實資料的備份步驟（避免切換造成不可回復的資料遺失）。
- **FR-011**: 新增的資料庫驅動相依 MUST 在實作計畫中說明必要性（滿足憲章額外限制）。

### Key Entities *(include if feature involves data)*

> 遷移**不改變**任何實體的語義或關係，只換底層儲存。既有實體維持原狀，包括（不限於）：

- **why_node（核心理解/候選）**：主張、認識論層次、佐證、來源錨點、出處範圍。
- **digest / entry / article（匯整/條目/文章語料）**：既有欄位與關聯。
- **conversation（對話：暫存/永久）**：訊息、標題、章節、與核心理解的由來連結。
- **source（來源）**：URL、標題、分類、脈絡、收進時間。
- **article（生成文章）**：主題、標題、Markdown、長度、難度、建立時間。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 既有 344 個測試在 Postgres 後端下 **100% 通過**、零行為回歸。
- **SC-002**: 在**無**可用資料庫的環境下，純核心測試仍 **100% 可執行並通過**（零安裝離線性質保住）。
- **SC-003**: 從空 Postgres 到應用可用（schema 建立＋啟動）**一步到位、可重複**，不需手動建表。
- **SC-004**: 以唯讀角色連線時，**100%** 的寫入嘗試被資料庫拒絕（唯讀為結構保證，非慣例）。
- **SC-005**: 遷移完成後，資料層**不再含任何 SQLite 相依**（`sqlite3` 不再被匯入於正式碼路徑）。
- **SC-006**: 範圍外項目（pgvector、多租戶、auth、領域分類、雙後端）**皆未被引入**本次變更。

## Assumptions

- **環境已具備 Postgres 能力**：已實測 Docker＋原生 Postgres＋psycopg3＋testcontainers 就緒、真 PG round-trip 通過。
- **測試用 Postgres 由容器提供**：整合測試以容器化 Postgres 起、per-test 乾淨資料庫；核心測試不需之。
- **連線資訊走環境變數**：沿用既有 `Config.from_env` 模式（原讀 `KNOWFIELD_DB`，改讀 Postgres 連線 env）。
- **這不是修憲**：憲章 IV＋額外限制本就允許「有需求＋在計畫說明必要性」時新增相依；本次放鬆的是 spec 級慣例
  「核心含 repository 零相依」，必要性＝部署 substrate（見 `history/084`）。
- **範圍嚴格限縮**：本次只做 SQLite→Postgres 的 parity 換血；pgvector、多租戶、auth、領域分類、公開分享
  皆排在其後、各自 promote，不在此範圍。
- **遷移順序**：本階段排在 auth 與領域分類之前（那兩者要加表/查詢，先換地基再蓋新房）。
