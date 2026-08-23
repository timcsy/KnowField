# 功能規格：對話清單的「聊出了東西」徽章讀對欄位（階段 18 缺陷）

**Feature Branch**: `main`（小刀）· **Created**: 2026-08-23 · **Status**: Draft

**知識庫來源**：階段 18（對話的由來）· `/knowie-next` 對正式庫審計時照出 · 前置 `repository.py:673` `conversation_referrers`

---

## ⚠️ 缺陷：UI 讀的不是事實來源

`repository.py:623` 自己寫著：

```python
if why_node_id is not None:    # 連結存 why_node 側（事實來源）
```

⇒ **`why_nodes.conversation_id` 是事實來源**。而 `conversations.why_node_id` 只在
`save_conversation(…, why_node_id=…)` 那一條路才被填——**冊封走的是 `promote_conversation`，
只更新 why_nodes 那側**。

而畫面讀的是後者（`ConversationsPage.tsx:73`、`ConversationSidebar.tsx:139`）。

**正式庫實測**：28 段對話中，真的是某條核心理解由來的有 **12** 段，畫面上顯示徽章的只有 **4** 段
⇒ **漏掉 8 段（真實數量的 2/3）**；反向誤標 0。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 看得出哪幾段聊出了東西 (Priority: P1)

使用者掃對話清單時，能看出哪幾段最後真的長成了核心理解。

**Why this priority**：這是階段 18 的反方向那一半。從根因回望對話已經 88% 通了（66/75），
從對話回望「這段聊出了什麼」只通 33%。**溯源是雙向的，只修好一邊等於沒修。**

**Independent Test**：對一段「冊封時綁了根因」的對話（走 `promote_conversation` 那條路），
清單上必須顯示徽章。

**Acceptance Scenarios**:

1. **Given** 一段對話有 N 條核心理解以它為由來（N≥1），**When** 看清單，**Then** 顯示徽章。
2. **Given** 一段沒有任何核心理解指向它的對話，**Then** 不顯示徽章。
3. **Given** N≥1，**Then** 徽章帶得出**數量**（比布林值有用，且同一個查詢就拿得到）。

---

### Edge Cases

- **兩條核心理解指向同一段對話** → 算一段、數量為 2。
- **核心理解被移除（status 非 anointed）** → ⚠️ 見 FR-004：以「有指向」為準，不看 status
  ——候選也是這段對話的產出，且與既有 `conversation_referrers` 的語意一致。
- **`conversations.why_node_id` 舊資料** → 不刪、不讀。

## Requirements *(mandatory)*

- **FR-001**：清單端點 MUST 由**事實來源**（`why_nodes.conversation_id`）判斷一段對話是不是由來。
- **FR-002**：MUST 一併回傳**數量**。
- **FR-003**：⚠️ MUST NOT 逐筆查詢——清單是 N 筆，要用**一次** `GROUP BY`。
- **FR-004**：判準 MUST 與既有 `conversation_referrers` 一致（有指向就算），不另立一套。
- **FR-005**：⚠️ MUST NOT 刪除或修改 `conversations.why_node_id` 欄
  ——加欄路徑（spec 044）明寫**不支援改型別或刪欄**；留著、停止讀它即可。
- **FR-006**：`/api/conversations` 的其餘欄位 MUST 逐字不變。

## Success Criteria *(mandatory)*

- **SC-001**：正式庫上，顯示徽章的對話數 **＝ 12**（不是 4）；誤標 **＝ 0**。
- **SC-002**：⚠️ 清單端點對 N 筆對話的查詢次數 **不隨 N 增長**。
- **SC-003**：`/api/conversations` 回傳中，既有欄位（`id`／`title`／`created_at`／`count`）逐字不變。
- **SC-004**：既有測試零回歸。

## Out of Scope

- 刪 `conversations.why_node_id` 欄。
- 接 `behavior_signals`（⚠️ 它的**消費者也不存在**——`沉降/decay` 在 `src/` 零命中，仍在 draft）。
- 文章存 `conversation_id`（另一刀）。
