# Implementation Plan: 匯出給 NotebookLM（複製 Markdown＋複製佐證網址）

**Branch**: `024-notebooklm-export` | **Date**: 2026-07-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/024-notebooklm-export/spec.md`

## Summary

在三個匯出點（`/chat` 當前對話、`/conversations/{id}` 存下的對話、`/roots` 每條冊封根因）各加兩顆鈕——**📋 複製 Markdown**（蒸餾內容 → NotebookLM 文字來源）、**🔗 複製佐證網址**（被引用 URL → NotebookLM URL 來源）。技術核心＝一個**零相依的純 formatter 模組**（primitives 進、字串／清單出），由 3 個 `text/plain` 端點呼叫；前端鈕 `fetch` 該端點取文字後 `navigator.clipboard.writeText` 複製、給 toast 提示。純唯讀：只讀既有 `conversations`／`why_nodes`，不寫庫、不改場、不碰 `build_field_system_prompt`。

## Technical Context

**Language/Version**: Python 3.12+（uv）

**Primary Dependencies**: 既有 FastAPI＋Jinja2（web 層）；**formatter 核心零第三方相依**（純 stdlib 字串組裝）

**Storage**: 既有 SQLite——**本功能只讀**（`conversations`、`why_nodes`），**不新增表、不改 schema**

**Testing**: pytest（現 368 綠）

**Target Platform**: 本機 web（單使用者）

**Project Type**: web（FastAPI＋Jinja2 templates）

**Performance Goals**: 匯出為即時字串組裝，O(訊息數)，人感即時

**Constraints**: 純唯讀、離線可測（formatter 不需 LLM／網路）、全繁中、核心零相依

**Scale/Scope**: 個人場規模（數十對話、數十根因）；新增 1 個純模組（4 函式）＋3 個端點＋三頁各兩顆鈕

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。*

- **I. TDD（不可妥協）** ✅ 先寫 formatter 純函式的失敗測試 → 實作 → 端點測試 → 前端鈕。每 US 一組。
- **II. 繁體中文** ✅ 規格／計畫／任務／鈕文字／提示全繁中。
- **III. 規格驅動** ✅ 本計畫可追溯 spec.md 的 FR-001…009。
- **IV. 簡潔／YAGNI** ✅ 新模組 `export/notebooklm.py` 是**隔離的純核心**（非增複雜度；反而把可測邏輯抽離 DB／web）；零新相依；不落庫。範圍外項（下載檔、LLM brief、直推 API）明確排除。
- **V. 可觀測性／明確錯誤** ✅ 空對話／無來源／缺欄位 → 合理輸出不崩（教訓 3）；前端複製失敗 → 明確繁中提示、不靜默。
- **VI. 使用者決策主權** ✅ 匯出是使用者主動、唯讀；不改場、不注入回對話（原則 6 純度）。

**結論：無違憲，無需複雜度豁免。**

## 關鍵設計決策（研究結論，詳見 research.md）

1. **純 formatter 模組、primitives 介面**：`src/knowfield/export/notebooklm.py`，函式收**基本型別**（title/messages/claim/ladder/urls），不 import models／repository → 零耦合、離線可單測、零相依。
2. **來源逐訊息呈現，非單一全域清單**：現況來源是**逐 assistant 訊息各自編號** `[1..]`（conversation.html 用 per-message `data-src-prefix` 佐證）。故 Markdown 把每則的來源塊**接在該則之後**，行內 `[n]` 才對得上；**不做**會撞號的全域底部清單。（修正 spec「底部來源清單」的措辭為「逐訊息來源塊」，更忠實。）
3. **端點回 `text/plain`、前端 fetch→複製**：三頁統一走「鈕 fetch 端點拿純文字 → `navigator.clipboard.writeText` → toast」，單一機制、都經過受測 formatter（單一事實來源）。`/chat` 走 POST（live history 在前端）；`/conversations/{id}`、`/roots/{id}` 走 GET。
4. **佐證網址＝去重、保序、每行一個**：跨全對話收集所有訊息來源 URL、去重保序；根因用其 `evidence_urls` 去重。

## Project Structure

### Documentation (this feature)

```text
specs/024-notebooklm-export/
├── plan.md              # 本檔
├── research.md          # Phase 0：設計決策與取捨
├── data-model.md        # Phase 1：既有實體（唯讀）＋衍生產物
├── quickstart.md        # Phase 1：驗證腳本
├── contracts/
│   └── export.md        # formatter 函式契約＋3 端點契約
└── tasks.md             # /speckit-tasks 產出（本命令不建）
```

### Source Code (repository root)

```text
src/knowfield/
├── export/                     # 【新】匯出純核心（零相依）
│   ├── __init__.py
│   └── notebooklm.py           # conversation_to_markdown / conversation_evidence_urls
│                               #   / why_node_to_markdown / dedup_urls（純函式）
└── web/
    ├── app.py                  # 【改】加 3 端點：POST /chat/export、
    │                           #   GET /conversations/{cid}/export、GET /roots/{wid}/export
    └── templates/
        ├── base.html           # 【改】加共用 copyExport() JS＋toast（複用 clipboard 慣例）
        ├── chat.html           # 【改】當前對話兩顆鈕
        ├── conversation.html   # 【改】兩顆鈕
        └── roots.html          # 【改】每條根因兩顆鈕

tests/unit/
├── test_export_notebooklm.py   # 【新】4 純函式（含空／無來源／缺欄位／去重）
└── test_export_web.py          # 【新】3 端點＋唯讀守衛（匯出不改庫／不動場脈絡）
```

**Structure Decision**: 沿用既有單一專案 web 結構。新增**一個隔離純模組** `export/`（可測核心），web 層只加 3 個薄端點＋模板鈕。無新表、無 schema 變更、無新相依。

## Complexity Tracking

> 無違憲項，無需填寫。（新模組 `export/` 是把可測邏輯自 DB／web 抽離，降複雜度而非增。）
