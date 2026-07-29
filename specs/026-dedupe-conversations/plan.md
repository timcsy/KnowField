# Implementation Plan: 既有重複對話清理（一次性、非破壞、人確認）

**Branch**: `026-dedupe-conversations` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/026-dedupe-conversations/spec.md`

## Summary

在「對話存檔」頁加「清理重複對話」：**純函式 `plan_dedupe(convos, provenance)`** 依內容指紋（複用 spec 025 `conversation_fingerprint`）分組、每組選留存（id 最大＝最新）、算「待刪份＋根因重指 old→new」計畫；**GET 預覽**（顯示計畫、不動資料）＋**POST 確認執行**（repo 執行層重指根因連結＋刪多餘份）。只併同指紋（非破壞）、異指紋不動、不改根因主張。無新表/新欄。

## Technical Context

**Language/Version**: Python 3.12+（uv）
**Primary Dependencies**: 既有 FastAPI＋Jinja2；計畫核心**零第三方相依**（純比較＋既有指紋）
**Storage**: SQLite——**只刪多餘 conversations 列＋UPDATE why_nodes.conversation_id**；不新增表/欄
**Testing**: pytest（現 414 綠）
**Target Platform**: 本機 web（單使用者）
**Project Type**: web（FastAPI＋Jinja2）
**Performance Goals**: 分組 O(對話數)，個人場規模即時
**Constraints**: 非破壞（只併同指紋）、兩段式人閘門、純函式計畫離線可測、全繁中、核心零相依
**Scale/Scope**: 一次性維護；1 純函式＋repo 2 方法＋1 預覽頁＋2 路由

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。*

- **I. TDD** ✅ `plan_dedupe` 先紅後綠（分組/選留存/重指/空/無重複/異指紋不動）；執行層有測（重指＋刪、非破壞）。
- **II. 繁中** ✅ 全繁中。
- **III. 規格驅動** ✅ 可追溯 FR-001…010。
- **IV. YAGNI** ✅ 複用 `conversation_fingerprint`；**無新表/欄**；計畫純函式與執行分離。
- **V. 可觀測性／錯誤** ✅ 預覽先看；空／無重複友善回報；不誤刪異指紋。
- **VI. 決策主權** ✅ 兩段式、**人確認才刪**、無自動/背景清理（原則 5）；刪除非破壞（同內容）。

**結論：無違憲。刪除為不可逆操作，以「預覽＋人確認＋只併同指紋（非破壞）」三重護欄守住。**

## 關鍵設計決策（詳見 research.md）

1. **計畫純函式、與執行分離**：`plan_dedupe(convos, provenance) -> DedupePlan`（分組/選留存/重指，純值、離線可測）；
   repo 執行層才真刪＋重指。預覽＝算計畫但不執行；確認＝重算計畫再執行（不信 client 帶回，單人本機安全）。
2. **留存＝id 最大（最新）**：保留最新標題/時間；該組其餘份的根因連結重指到它。
3. **只併同指紋**（`conversation_fingerprint`，忽略標題等易變欄）：異指紋（#18/#19 65/70 句）天然分組不同 → 不動。
4. **重指用既有 why_node 側連結**：`UPDATE why_nodes SET conversation_id=留存` for 指向待刪份者；刪多餘 conversations 列。
   根因主張/階梯**完全不碰**（FR-006）。清理後 `why_node_provenance` 每條仍連得到（留存份）。

## Project Structure

### Documentation (this feature)
```text
specs/026-dedupe-conversations/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/dedupe.md
└── tasks.md（/speckit-tasks 產出）
```

### Source Code (repository root)
```text
src/learnnews/
├── chat/
│   └── capture.py              # 【改】加 plan_dedupe(convos, provenance)->DedupePlan（純函式，複用 fingerprint）
├── store/
│   └── repository.py           # 【改】dedupe_plan()（算計畫、不動資料）＋apply_dedupe()（重指 why_nodes.conversation_id＋刪多餘份）
└── web/
    ├── app.py                  # 【改】GET /conversations/dedupe（預覽）＋POST /conversations/dedupe（確認執行→redirect）
    └── templates/
        ├── conversations.html  # 【改】頁首加「🧹 清理重複對話」鈕（→ 預覽）＋清理後結果 flash
        └── dedupe.html         # 【新】預覽頁：N 組/M 份多餘/K 根因重指＋「確認清理」(POST)＋「取消」

tests/unit/
├── test_capture_core.py        # 【擴】plan_dedupe：分組/選留存/重指/空/無重複/異指紋不動/未連根因份
└── test_dedupe_web.py          # 【新】預覽不動資料；確認後同組留 1、根因重指、異指紋不動、根因主張不變；空庫友善；人閘門(GET 不刪)
```

**Structure Decision**: 沿用單一 web 專案。計畫邏輯進既有純核心 `chat/capture.py`（與 fingerprint 同家）；repo 加算計畫＋執行兩法；web 加預覽頁＋2 路由。無新表、無新欄、無新相依。

## Complexity Tracking

> 無違憲項，無需填寫。（複用既有指紋與 why_node 連結；計畫純函式與執行分離＝降風險，非增複雜度。）
