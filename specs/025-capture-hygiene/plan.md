# Implementation Plan: 對話收料的漏——去重＋收尾缺口提醒

**Branch**: `025-capture-hygiene` | **Date**: 2026-07-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/025-capture-hygiene/spec.md`

## Summary

修 spec 023 真實使用照出的兩個漏：
- **#1 去重**：讓 `save_conversation` **依內容指紋冪等**（同一段對話多次連同存 → 回既有 id、不新增複本），並把「由來」連結**存在 why_node 側**（`why_nodes.conversation_id`，多條根因可共用一份對話）。機制對既有 anoint 流幾乎透明——只需 save 冪等＋連結改邊。
- **#2 收尾缺口提醒**：純函式 `distill_gap(總長, 上次收位置, 門檻)` 判是否提醒＋未收區間；chat 頁以 client 記的「上次整理長度」餵它，長且尾段未收才顯示溫和提醒；**只提醒、不自動冊封**（原則 5）。

## Technical Context

**Language/Version**: Python 3.12+（uv）
**Primary Dependencies**: 既有 FastAPI＋Jinja2；判準／指紋核心**零第三方相依**（stdlib `hashlib`／純比較）
**Storage**: SQLite——**加一欄** `why_nodes.conversation_id`（冪等 migrate）；不新增表
**Testing**: pytest（現 393 綠）
**Target Platform**: 本機 web（單使用者）
**Project Type**: web（FastAPI＋Jinja2）
**Performance Goals**: 指紋 O(對話長度)、判準 O(1)，人感即時
**Constraints**: 去重不刪改既有存檔、判準純函式離線可測、人閘門、全繁中、核心零相依
**Scale/Scope**: 個人場規模；1 欄位＋2 純函式＋repo 改 3 處＋chat 頁提醒 UI

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。*

- **I. TDD** ✅ 指紋去重與 `distill_gap` 先紅後綠；repo 去重／provenance 改邊有測；守衛測（不自動冊封、不刪既有）。
- **II. 繁中** ✅ 全繁中。
- **III. 規格驅動** ✅ 規劃期發現「stable-id 不可行→改內容指紋」，**已回頭更正 spec Assumption**（本檔 research D1 記因果）。
- **IV. YAGNI** ✅ 用**一個欄位**（`why_nodes.conversation_id`）表達「一份↔多條」，不引連結表；#1 靠「save 冪等＋連結改邊」，不改 anoint UX；#2 不落庫（client 記上次長度）。
- **V. 可觀測性／錯誤** ✅ 空／缺欄位→判準回「不提醒」不崩；去重對壞輸入不誤併。
- **VI. 決策主權** ✅ 提醒不自動收；去重只加不刪。

**結論：無違憲。唯一結構變更＝`why_nodes` 加一欄，屬正當（表達新的「一份對話↔多條根因」關係，教訓 8 記一筆）。**

## 關鍵設計決策（詳見 research.md）

1. **連結改存在 why_node 側**：加 `why_nodes.conversation_id`（可空）。`why_node_provenance()` 改讀它 → 天然支援「多條根因共用一份對話」。既有 `conversations.why_node_id` 保留（歷史相容、首作者），不再是事實來源；migrate 把既有對話的 `why_node_id` 回填到對應 why_node。
2. **去重＝內容指紋冪等 save**：`conversation_fingerprint(messages)`（純函式，stdlib hash）。`save_conversation` 先查同指紋是否已存 → 有則回既有 id、無則插入。多次連同存同一段 → 一份；不同段 → 各份（FR-003 不誤併）。
3. **#2 判準純函式**：`distill_gap(total, last_captured, min_total, gap_threshold)`→ `None` 或 `(from, to)`。web 由 client（localStorage 記「上次按整理/冊封時的訊息數」）餵入；純函式離線可測、門檻集中一處易調。
4. **不動 anoint UX、不做 AJAX**：#1 靠後端冪等，前端零改；#2 只在 chat 頁加一塊提醒（讀 client 狀態＋呼叫既有 distill 入口）。

## Project Structure

### Documentation (this feature)
```text
specs/025-capture-hygiene/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/capture-hygiene.md
└── tasks.md（/speckit-tasks 產出）
```

### Source Code (repository root)
```text
src/knowfield/
├── chat/
│   └── capture.py              # 【新】純核心：conversation_fingerprint / distill_gap（零相依）
├── store/
│   ├── schema.py               # 【改】why_nodes 加 conversation_id 欄（SCHEMA＋_migrate 冪等回填）
│   └── repository.py           # 【改】save_conversation 指紋冪等；連結寫 why_nodes.conversation_id；
│                               #   why_node_provenance 改讀 why_nodes 側；delete_why_node 清該連結
└── web/
    ├── app.py                  # 【改】chat 頁帶收尾提醒判準結果；anoint 流沿用（去重自動生效）
    └── templates/
        └── chat.html           # 【改】收尾缺口提醒區塊（client 記上次整理長度、呼叫既有整理入口）

tests/unit/
├── test_capture_core.py        # 【新】fingerprint（同/異/空/缺欄位）＋distill_gap（長短/剛收/邊界）
└── test_capture_hygiene_web.py # 【新】同段 N 冊封→一份 N 連結；異段不誤併；獨立冊封不增；
                                #   provenance 改邊後 spec023 行為不回歸；提醒顯示/隱藏；不自動冊封守衛
```

**Structure Decision**: 沿用單一 web 專案。新增一個**純核心模組** `chat/capture.py`（指紋＋判準，可測、零相依）；schema 加一欄（冪等 migrate）；repo 改 3 處；chat 頁加提醒。無新表、無新相依。

## Complexity Tracking

| 變更 | 為何需要 | 較簡替代被否原因 |
|---|---|---|
| `why_nodes` 加 `conversation_id` 欄 | 表達「一份對話↔多條根因」（現況一對一表達不了） | 連結表：本關係是多對一（根因→對話），一欄即足，連結表過度；內容比對取代欄位：無法穩定連結、且要重算 |
