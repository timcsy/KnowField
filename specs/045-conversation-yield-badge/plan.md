# Implementation Plan：對話清單的由來徽章讀對欄位

**Branch**: `main` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

## Summary

`repository` 加一個 `conversation_yield_counts()`（一次 `GROUP BY`），
`/api/conversations` 用它產出 `yield_count`；前端徽章改讀那個數字。

## Constitution Check

| 原則 | 本刀怎麼過 |
|---|---|
| **I. TDD** | ⚠️ FR-003（不逐筆查）是**效能**斷言，綠燈看不出來 → 要用**計數 execute 次數**的測試釘住 |
| **IV. YAGNI** | 不刪欄、不加表、不動 `conversation_referrers` |
| **V. 可觀測性** | 不需要 log——這是讀取路徑 |
| **VI. 主權** | 純顯示修正，不改變任何使用者決定 |

## Phase 0：Research

### D1. 判準 → **沿用 `conversation_referrers` 的「有指向就算」**

- ⚠️ **否決：只算 `status='anointed'`。** 那會跟既有的 `conversation_referrers`
  （`repository.py:673`，不看 status）**兩套語意**，同一件事在兩個地方給不同答案
  ——本週已經因為「兩個欄位、讀錯一個」吃過虧（本刀就是），不要再造第二個。

### D2. 效能 → **一次 `GROUP BY`，不是逐筆**

- `SELECT conversation_id, count(*) FROM why_nodes WHERE conversation_id IS NOT NULL GROUP BY 1`
- ⚠️ 這條要**測得到**：純看輸出分不出逐筆與批次。用一個會數 `execute` 次數的假 conn 釘住
  （`experience.md`：一條沒有被錯誤實作撞過的測試，不知道自己在測什麼）。

### D3. 舊欄位 → **留著，停止讀**

- 刪欄不在加欄路徑的能力內（spec 044 明寫），而且它有舊資料。
- ⓘ 代價講明：`conversations.why_node_id` 從此是**死欄位**。它已被記在本 spec 的 out of scope；
  真要清要另外決定。

## Phase 1：契約

`GET /api/conversations` 每筆新增 `yield_count: int`（0＝沒聊出東西）。
`why_node_id` **仍照舊回傳**（前端不再讀，但拿掉會是破壞性變更，不必要）。

## Complexity Tracking

無違規。
