# 實作計畫：來源簡體中文正規化為繁體（顯示層）

**Branch**: `037-simplified-to-traditional` | **Date**: 2026-08-18 | **Spec**: [spec.md](./spec.md)

**Input**: `/specs/037-simplified-to-traditional/spec.md`

## Summary

把收進的簡體中文來源，在**詳情頁的讀取路徑**上轉為繁體（含詞彙在地化），儲存層完全不動。
用確定性引擎 `opencc-python-reimplemented`（`s2twp`），零 LLM。**核心工程風險是承重片段**
——實測顯示未保護的轉換會改壞程式碼識別字、URL、圖片路徑與數學下標，因此「抽佔位 → 轉換 → 塞回」
是這個功能的主體，而不是配角。引擎走可插拔介面，不可用時回傳原文。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `opencc-python-reimplemented`（新增，純 Python、無 C 相依、可選）

**Storage**: 不涉及寫入。讀取沿用既有可攜資料層（本地 SQLite／prod PG 雙後端）

**Testing**: pytest（現有 369 個 test 函式）

**Target Platform**: Linux 容器（prod，k3s）＋ macOS 本機開發

**Project Type**: Web service（FastAPI 後端 ＋ React 前端）

**Performance Goals**: 顯示轉換造成的額外延遲 < 200ms（SC-003）

**Constraints**: 不寫回儲存層；承重片段逐字不變；引擎缺席時不得中斷

**Scale/Scope**: 單人使用；單篇來源正文（數千至數萬字元）

## Constitution Check

*GATE：Phase 0 前必過，Phase 1 後複查。*

| 原則 | 評估 | 結果 |
|---|---|---|
| **I. TDD 不可妥協** | 純函式為主（文字進、文字出），是最容易先寫測試的形態。承重保護的六個危險案例已有實測資料，直接變成測試案例。 | ✅ 通過 |
| **II. 繁體中文文件** | spec／plan／research／tasks 全繁中；程式碼註解繁中。 | ✅ 通過 |
| **III. 規格驅動** | spec 先行且已通過品質檢查表；實作可追溯至 FR-001~009。 | ✅ 通過 |
| **IV. 簡潔與 YAGNI** | 只新增一個純 Python 可選相依與一個文字模組；不建對照 UI、不建設定系統、不動儲存層。 | ✅ 通過 |
| **V. 可觀測性與錯誤處理** | 引擎不可用是**預期路徑**不是例外，回傳原文並記一次結構化日誌；不靜默吞例外。 | ✅ 通過 |
| **VI. 使用者保有決策主權** | ⚠️ **這條是本功能最實質的約束**。自動轉換改變了使用者所見，憲章要求「可檢視、可修改、**可覆寫**」。 → 必須提供**看原文的出口**（前端一個切換，非並置對照）。若只做後端轉換而不給出口，**本功能違憲**。 | ⚠️ 有條件通過——見下 |

**VI 的結論**：FR-005（原文可取回）必須兌現到**使用者可及的層面**，不能只停在 API。
計畫因此包含一個最小切換（繁體 ⇄ 原文），它**不是** spec 排除的「對照 UI」——對照是**並置**，
切換是**擇一顯示**，兩者不同。這是憲章要求的最小形態，不是範圍擴張。

## Project Structure

### Documentation (this feature)

```text
specs/037-simplified-to-traditional/
├── plan.md              # 本檔
├── research.md          # Phase 0：引擎選型與危險案例實測
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   └── api-source.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks 產出，非本階段
```

### Source Code (repository root)

```text
src/knowfield/
├── text/                        # 新增：顯示層文字處理
│   ├── __init__.py
│   ├── protect.py               # 承重片段抽佔位／塞回（純函式）
│   └── s2t.py                   # 簡→繁介面 + OpenCC 後端 + identity fallback
└── web/
    └── app.py                   # `/api/source` 讀取路徑套用轉換（唯一接點）

frontend/src/
└── SourcePage.tsx               # 「繁體 ⇄ 原文」切換（憲章 VI）

tests/
├── unit/
│   ├── test_text_protect.py     # 六個危險案例：程式碼／URL／圖片／數學塊／行內數學／行內 code
│   └── test_text_s2t.py         # 詞彙轉換、繁體逐字不變、英文不變、引擎缺席 fallback
└── contract/
    └── test_web_source_s2t.py   # `/api/source` 回傳繁體、`?raw=1` 回傳原文
```

**Structure Decision**：新增 `src/knowfield/text/` 而非塞進 `ingest/`。理由：`ingest/` 的語義是
**進料**（寫入方向），而本功能嚴格屬**顯示**（讀取方向）。放進 `ingest/` 會讓後人以為它會寫回，
正是 FR-004 要防的誤解。純函式與副作用隔離：`protect.py`／`s2t.py` 皆為純函式，唯一的 I/O 邊界在
`web/app.py`。

## Complexity Tracking

> 僅在 Constitution Check 有需要辯護的違反時填寫。

| 項目 | 為何需要 | 為何不能更簡單 |
|---|---|---|
| 新增 `text/` 模組（而非寫在 `app.py` 內） | 承重保護是純函式且測試量大（六個危險案例＋邊界），內嵌在 route 裡無法單元測試 | 直接寫在 route ⇒ 只能靠 HTTP 層測試，違反憲章 I 的 Red-Green 節奏 |
| 前端切換（繁體 ⇄ 原文） | 憲章 VI 要求可覆寫；純後端轉換會讓使用者失去對所見內容的控制 | 不做 ⇒ 違憲；做成並置對照 ⇒ 超出 spec 範圍且是第二刀的事 |

無其他複雜度需要辯護。
