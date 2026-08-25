# Implementation Plan：對話裡看得見冊封狀態（階段 41）

**Branch**: `main` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

## Summary

三件接線 ＋ 一件新：
① `conversation_referrers` 帶回 `src_from/src_to` → 對話詳情多一個 `anointed`
② 前端逐則標覆蓋（**集合，不是水位線**）
③ 對話頁候選卡改成可編輯（沿用來源頁那張）
④ 重新冊封＝新增一條（既有去重擋相同文字，**不用寫新程式**）

## Constitution Check

| 原則 | 本刀怎麼過 |
|---|---|
| **I. TDD** | ⚠️ FR-002 是「形狀」斷言——**水位線實作也會綠**，除非測試特地放一個**中間的洞**。SC-002 就是那條反向攻擊 |
| **IV. YAGNI** | 不加表、不加欄、不新做卡片元件；`distill_gap` 已存在，只是接上 |
| **VI. 主權** | 候選可編輯＝把冊封的最後一哩交回人手上（原則 5） |

## Phase 0：Research

### D1. 覆蓋怎麼算 → **union of ranges，前端算**

- 後端回 `anointed: [{id, claim, from, to}]`；前端 `covered = ⋃[from..to]`。
- ⚠️ **否決水位線 `max(src_to)`**：實測對話 44 收到 46 卻缺 3–8、對話 31 缺 [1,2,9–12]。
  水位線會把洞藏起來——而洞正是使用者要找的。
- **否決後端回一個 boolean 陣列**：訊息數會變（接著聊），陣列會過期；回範圍讓前端當下算才不會錯位。

### D2. 沒有範圍的舊冊封 → **只標對話層級**

- 41/75 有範圍、34 沒有。⚠️ **不猜**——猜就是造假資料（同 spec 044 對既有 28 段對話的處理）。

### D3. 候選可編輯 → **沿用 `SourceCandidateCard` 的形狀**

- 後端**早就收**改過的 `claim`／`kind`（`_do_anoint(claim, …, kind, …)`）⇒ **純前端改動**。
- ⚠️ 否決另做一張卡：本週才因為「同一件事兩套」吃過虧（spec 045 的兩個欄位）。

### D4. 重新冊封 → **不用寫新程式**

- 既有 `norm_claim` 去重：相同文字回 `status="exists"`；改過文字自然新增一條。
- ⇒ FR-006／FR-007 已經成立，只需要**測試釘住**，避免日後有人「順手」改成 upsert。

## Phase 1：契約

`GET /api/conversations/{cid}` 新增：

```json
"anointed": [{"id": 88, "claim": "…", "from": 40, "to": 46}]
```

`referrers` **照舊回傳**（前端仍用它擋編輯／重生）。

## Complexity Tracking

無違規。
