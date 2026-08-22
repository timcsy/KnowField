# Implementation Plan：帶入物的由來落庫（階段 40）

**Branch**: `main`（小刀）| **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

## Summary

兩件事：① `init_db` 多一步**冪等補欄**（宣告式清單，兩後端）②
`conversations` 加 `carried_kind` / `carried_ref`，在 autosave **建立那筆時**寫入。

## Technical Context

**Language/Version**: Python 3.11 ＋ React 19（前端只多傳兩個欄位，無可見元素）
**Storage**: `conversations` ＋2 欄；**這是專案第一次對既有表加欄**
**Testing**: pytest（unit ＋ contract）；PG 那半靠 `KNOWFIELD_TEST_BACKEND=postgres`
**Constraints**: 舊資料不動；模型脈絡逐字不變；介面零可見元素

## Constitution Check

| 原則 | 本刀怎麼過 |
|---|---|
| **I. TDD** | ⚠️ FR-004（舊資料不動）與 FR-007（脈絡不變）是沉默失效型，兩條要反向攻擊 |
| **II. 繁中** | 全繁中 |
| **III. 規格驅動** | vision 階段 40（人 commit）→ spec → plan → tasks |
| **IV. YAGNI** | 只加兩欄、只在 INSERT 寫、不做 UI。補欄機制是**宣告式一張表**，不是 migration 框架 |
| **V. 可觀測性** | 補欄時記一行 log（哪張表加了哪欄）——這是**只會發生一次**的事，事後查得到很重要 |
| **VI. 主權** | 不改變任何使用者可見行為 |

## Phase 0：Research

### D1. 怎麼判斷欄存不存在 → **先問，再加**

- **SQLite**：`PRAGMA table_info(<t>)` → 每列的 `name`
- **PG**：`SELECT column_name FROM information_schema.columns WHERE table_name=%s`
- ⚠️ **否決：`ALTER TABLE … ADD COLUMN` 包 try/except 吞例外。**
  那會把「欄已存在」跟「型別寫錯／表不存在／權限不足」混成同一件事 ⇒
  真的錯了也靜默過去。這正是本專案這兩天連續撞到的那類 bug（`history/102`、`104`）。
- ⚠️ **否決：`ADD COLUMN IF NOT EXISTS`。** PG 有，**SQLite 沒有** ⇒ 破雙後端 parity（spec 036）。

### D2. 宣告在哪 → `schema.py` 的一張清單，`init_db` 收尾時跑

```python
_ADD_COLUMNS = [("conversations", "carried_kind", "TEXT DEFAULT ''"), ...]
```

- 理由：跟 `SCHEMA` 放在一起，加欄這件事就只有**一個**地方要看。
- **否決：獨立的 migration 目錄／版本號。** 單人專案、一張清單就夠（YAGNI）。
  ⓘ 代價講明：這個作法**不支援改型別或刪欄**。真的需要時再升級，不預先蓋。

### D3. 由來寫在哪 → `autosave_temporary` 的 **INSERT 分支**

- UPDATE 分支**一個字都不動** ⇒ FR-006（不被改寫）是結構性的，不靠自律。
- 前端把 `carried` 一起送進 autosave；沒帶就送空字串，行為與現況相同。

### D4. 記什麼 → `carried_kind` ∈ {'', 'article', 'source'}、`carried_ref` = 文章 id 或來源 url

- 兩欄而不是一欄 `article:12`：查詢時不用拆字串。
- **不做外鍵**：文章／來源被刪之後，「這段對話當初是從它來的」仍是歷史事實。

## Phase 1：Design

### 契約

`POST /api/chat/autosave` 新增可選 `carried_kind` / `carried_ref`：

| 情況 | 行為 |
|---|---|
| 新建那筆 ＋ 有帶 | 寫入由來 |
| 新建那筆 ＋ 沒帶 | 由來為空（與現況逐字相同） |
| 更新既有那筆 | **由來完全不碰**（不論有沒有送） |

### 資料

`conversations` ＋ `carried_kind TEXT DEFAULT ''`、`carried_ref TEXT DEFAULT ''`。

## Complexity Tracking

無違規。
