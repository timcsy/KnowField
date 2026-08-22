# 功能規格：帶入物的由來落庫（階段 40）

**Feature Branch**: `main`（小刀）· **Created**: 2026-08-22 · **Status**: Draft

**知識庫來源**：vision 階段 40 · 設計源 [`draft/2026-08-22-帶入物的由來要落庫.md`](../../knowledge/draft/2026-08-22-帶入物的由來要落庫.md) · 前置 spec 041／042

---

## ⚠️ 問題不是「沒人用」，是「量不到」

`conversations` 的欄位裡沒有任何一個記錄「這段是帶著文章／來源開的」。
而 spec 041 FR-003 **刻意**讓帶入物不進 `messages`（擋 model collapse，那是對的）
⇒ 儲存層零痕跡 ⇒ `audit-field-usage` 永遠查不到。

**報告上的空白分不出「沒人用」和「量不到」。** 這一刀把那個空白變成一個真的數字。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 既有資料庫加得了欄 (Priority: P1)

**Why this priority**：這是地基。⚠️ 專案目前**不會加欄**（`schema.py:148`：「不含舊 SQLite 檔的
`_migrate` 補欄」），而 `CREATE TABLE IF NOT EXISTS` 對既有表是 no-op ⇒
正式庫那 28 段對話所在的表不會長出新欄，新程式一寫就炸。

**Independent Test**：建一個「舊」資料庫（缺欄、有資料），跑一次 `init_db`，
新欄出現、**舊資料一列都沒動**。

**Acceptance Scenarios**:

1. **Given** 一個缺欄且有資料的資料庫，**When** `init_db`，**Then** 欄補上、資料不變。
2. **Given** 欄已存在，**When** 再跑 `init_db`，**Then** 不報錯、不重複加（冪等）。
3. **Given** 兩種後端（SQLite／PG），**When** 各跑一次，**Then** 行為相同。

---

### User Story 2 - 帶著文章／來源開的對話，事後查得出 (Priority: P1)

**Independent Test**：帶著一篇文章開一段新對話並自動存檔，事後從資料庫查得出它的由來。

**Acceptance Scenarios**:

1. **Given** 帶了文章的新對話，**When** autosave 建立那筆，**Then** 由來記為 `article` ＋ 該 id。
2. **Given** 帶了來源，**Then** 記為 `source` ＋ 該 url。
3. **Given** 沒帶任何東西，**Then** 由來為空。
4. **Given** 同一段對話後續又 autosave 多次，**Then** 由來 **不變**（只在建立時寫）。

---

### User Story 3 - 這是元資料，不是內容 (Priority: P1)

**Why this priority**：與 P1 並列。041 FR-003 的閘門（冊封候選不得由文章原文生成）
靠的是「帶入物不進 `history`」。這一刀若讓任何帶入物內容漏進 `messages` 或模型脈絡，就破了它。

**Independent Test**：帶入物由來落庫前後，送給模型的訊息**逐字相同**。

---

### Edge Cases

- **既有的 28 段對話** → 由來為空。⚠️ **不得**回頭猜著補寫——那是造假資料。
- **同一段對話被接回、再帶別的東西** → 由來仍是**最初**那個（它記的是「從哪來的」）。
- **文章／來源事後被刪** → 由來仍留著（它是歷史事實，不是外鍵）。

## Requirements *(mandatory)*

- **FR-001**：系統 MUST 能對**既有且有資料**的資料庫補上缺少的欄，且 MUST 冪等。
- **FR-002**：補欄 MUST 在 SQLite 與 Postgres 上行為相同。
- **FR-003**：⚠️ 補欄 MUST **先查詢欄是否存在**再決定要不要加；
  MUST NOT 用 try/except 硬加後吞掉例外——那會把「已存在」與「真的錯了」混成同一件事（沉默失敗）。
- **FR-004**：補欄 MUST NOT 改動任何既有資料列。
- **FR-005**：帶著文章／來源開的對話，其由來（kind ＋ ref）MUST 在該對話**被建立時**寫入。
- **FR-006**：由來 MUST NOT 在後續更新中被改寫。
- **FR-007**：⚠️ 由來 MUST NOT 進入 `messages`，且送給模型的脈絡 MUST **逐字不變**。
- **FR-008**：⚠️ 由來 MUST NOT 出現在任何使用者介面——沒有計數器、沒有標記、沒有設定。
- **FR-009**：`audit-field-usage` MUST 讀得到這個數字。
- **FR-010**：沒帶任何東西時，行為 MUST 與現況**逐字相同**。

## Success Criteria *(mandatory)*

- **SC-001**：缺欄且有 N 列資料的舊庫跑 `init_db` 後，欄數 ＋2、資料列數仍為 N、內容逐字不變。
- **SC-002**：連跑三次 `init_db` 不報錯，欄不重複。
- **SC-003**：帶文章開的對話，DB 中由來 ＝ (`article`, 該 id)；帶來源 ＝ (`source`, 該 url)；沒帶 ＝ 空。
- **SC-004**：同一段對話 autosave 三次後，由來與第一次**相同**。
- **SC-005**：⚠️ 落庫前後，送給模型的訊息 **逐字相同**。
- **SC-006**：`frontend/` 中與「由來顯示」有關的可見元素 ＝ 0。
- **SC-007**：既有測試零回歸。

## Assumptions

- 由來只記**最初**那一個帶入物；多次帶入不累積（YAGNI，且「從哪來的」本來就只有一個）。
- 既有 28 段對話的由來留空，不追溯。

## Out of Scope

- 計數器 UI、儀表板。
- 文章存 `conversation_id`（可以，但那是下一刀——本刀只蓋加欄的地基）。
- 追溯補寫既有對話的由來。
