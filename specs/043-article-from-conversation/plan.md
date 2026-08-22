# Implementation Plan：從對話生文章（階段 39，第一刀）

**Branch**: `main`（小刀）| **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

## Summary

`generate_article` 多一個 `pinned` 參數：那些節點**必被考慮**、排在最前，
但仍走**同一條** kind 分流（`已證實/推論`→正文、`類比/猜想`→延伸閱讀）。
路由多一個可選 `conversation_id`，用 `conversation_referrers` 取 pinned。前端加一個入口。

## Technical Context

**Language/Version**: Python 3.11 ＋ React 19
**Primary Dependencies**: 既有 `output/article.py`、`store/repository.py`
**Storage**: **無 schema 改動**（見 spec Out of Scope 的補欄陷阱）
**Testing**: pytest（unit ＋ contract）
**Constraints**: 未帶對話時逐字相同；不動任何已儲存內容

## Constitution Check

| 原則 | 本刀怎麼過 |
|---|---|
| **I. TDD** | ⚠️ FR-002（不依賴檢索）與 FR-003（分層不被繞過）是沉默失效型，兩條都要反向攻擊 |
| **II. 繁中** | 全繁中 |
| **III. 規格驅動** | vision 階段 39（人 commit，量過數字才升）→ spec → plan → tasks |
| **IV. YAGNI** | 不加表、不加欄、不做 brief、不重取標題。`generate_article` 只多一個參數 |
| **V. 可觀測性** | 生成時記一行：pinned 幾條、補了幾條、正文/延伸各幾條 |
| **VI. 主權** | 人明確按才走這條；未帶對話時行為不變 |

## Phase 0：Research

### D1. 釘住怎麼實作 → **排序時把 pinned 提到最前，分流規則完全不動**

- 決定：`ranked = pinned_in_order + [其餘依 _rank_by_topic 排序]`（去重），
  之後**沿用原本那兩行**做 kind 分流與 `[:top_k]`。
- 理由：**分流那兩行一個字都不改**，就不可能繞過分層（FR-003 變成結構性的，不是靠自律）。
- **否決 A：把 pinned 直接塞進 `body`**。那會讓 `猜想` 進正文 —— 破掉「高證實」賣點。
  ⚠️ 這不是假想：實測對話 #20 就有一條 `猜想`。
- **否決 B：把 pinned 當 `topic` 字串去檢索**。檢索沒選中就沉默漏掉，正是 FR-002 要擋的。

### D2. 補滿從哪來 → **場內其餘已冊封節點，依與對話標題的相關度**

- `_rank_by_topic(nodes, topic, embedder)` 已在（`output/article.py:39`），topic 用對話標題。
- **否決：合成一個 query（把 referrers 的 claim 串起來）**。多一個沒驗過的步驟，
  而對話標題本來就是「反映落點/全貌」的一句（`fc.title`）——YAGNI。

### D3. 空 referrers → **路由回一個可行動的訊息，不是空文章**

- 沿用現行 `empty` 那條路的形狀，但訊息指向「先精選」。

### D4. ⚠️ 不做的事：文章存 `conversation_id`

- `articles` 是既有表，專案**無補欄機制**（`schema.py:148`）。硬做會在正式環境靜默失敗。
- 這條的正確做法是先補一個 `ALTER TABLE … ADD COLUMN IF NOT EXISTS` 的遷移路徑（兩後端都要驗），
  那是另一刀。

## Phase 1：Design

### 契約

`POST /api/article` 新增可選 `conversation_id`：

| 情況 | 行為 |
|---|---|
| 有 `conversation_id` 且該對話有 referrers | pinned ＝ referrers；`topic` 預設取對話標題 |
| 有 `conversation_id` 但 referrers 為空 | 回 `{"error": "這段對話還沒精選出核心理解——先精選，再用它生文章。"}`（200） |
| 無 `conversation_id` | 與現況**逐字相同** |

前端：對話頁「⋯ 更多」加一顆「📝 用這段生一篇文章」→ 帶 `conversation_id` 去 `/articles`。

## Complexity Tracking

無違規。
